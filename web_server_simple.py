from flask import Flask, render_template, request, jsonify, send_file
import json
import os
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import io
import base64
from collections import OrderedDict
import numpy as np

app = Flask(__name__)
app.config['SECRET_KEY'] = 'click-counter-secret'
app.config['UPLOAD_FOLDER'] = 'sessions'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def setup_russian_font():
    font_paths = [
        'C:/Windows/Fonts/arial.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
    ]
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            fm.fontManager.addfont(font_path)
            font_name = fm.FontProperties(fname=font_path).get_name()
            plt.rcParams['font.family'] = font_name
            break

setup_russian_font()

@app.route('/')
def index():
    sessions = []
    
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        if filename.endswith('.json'):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                    sessions.append({
                        'id': session_data.get('session_id', filename),
                        'filename': filename,
                        'total_clicks': session_data.get('total_clicks', 0),
                        'timestamp': session_data.get('timestamp', ''),
                        'minutes': len(session_data.get('clicks_per_minute', {})),
                        'button_stats': session_data.get('button_stats', {})
                    })
            except:
                continue
    
    sessions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    return render_template('index.html', sessions=sessions)

@app.route('/api/session', methods=['POST'])
def receive_session():
    try:
        data = request.get_json()
        
        if not data or 'session_id' not in data:
            return jsonify({'error': 'Неверный формат данных'}), 400
        
        session_id = data['session_id']
        filename = f"{session_id}.json"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'status': 'success',
            'session_id': session_id,
            'message': 'Данные сессии сохранены',
            'graph_url': f'/session/{session_id}'
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/session/<session_id>')
def show_session(session_id):
    filename = f"{session_id}.json"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.exists(filepath):
        return "Сессия не найдена", 404
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            session_data = json.load(f)
        
        # Создаем графики
        plot_url = create_click_plot(session_data)
        button_plot_url = create_button_plot(session_data) if 'button_stats' in session_data else None
        
        return render_template('session.html', 
                             session=session_data,
                             plot_url=plot_url,
                             button_plot_url=button_plot_url)
        
    except Exception as e:
        return f"Ошибка при обработке данных: {str(e)}", 500

def create_click_plot(session_data):
    """Создает график кликов по минутам"""
    clicks_data = session_data.get('clicks_per_minute', {})
    
    if not clicks_data:
        return None
    
    sorted_data = OrderedDict(sorted(clicks_data.items(), key=lambda x: int(x[0])))
    
    minutes = [f"{int(m)+1}" for m in sorted_data.keys()]
    clicks = list(sorted_data.values())
    
    # Создаем график
    fig, ax = plt.subplots(figsize=(12, 6))
    
    colors = plt.cm.viridis(np.linspace(0, 0.8, len(clicks)))
    bars = ax.bar(minutes, clicks, color=colors, edgecolor='black', alpha=0.8)
    
    # Добавляем значения
    for bar, click in zip(bars, clicks):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                f'{click}', ha='center', va='bottom', fontsize=9)
    
    # Настройки
    ax.set_title(f'Клики в минуту - Сессия: {session_data.get("session_id", "")}', 
                fontsize=14, fontweight='bold', pad=20)
    ax.set_xlabel('Минута', fontsize=12)
    ax.set_ylabel('Количество кликов', fontsize=12)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    # Поворачиваем подписи если много минут
    if len(minutes) > 10:
        plt.xticks(rotation=45, ha='right')
    
    # Автоматический предел оси Y
    if clicks:
        ax.set_ylim(0, max(clicks) * 1.2)
    
    plt.tight_layout()
    
    # Сохраняем в base64
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode('utf-8')
    
    return f"data:image/png;base64,{image_base64}"

def create_button_plot(session_data):
    """Создает круговую диаграмму распределения кликов по кнопкам"""
    button_stats = session_data.get('button_stats', {})
    
    if not button_stats or sum(button_stats.values()) == 0:
        return None
    
    labels = ['ЛКМ', 'ПКМ', 'СКМ']
    sizes = [button_stats.get('left', 0), 
             button_stats.get('right', 0), 
             button_stats.get('middle', 0)]
    
    # Убираем нулевые значения
    filtered_labels = []
    filtered_sizes = []
    colors = []
    color_map = {'ЛКМ': '#ff9999', 'ПКМ': '#66b3ff', 'СКМ': '#99ff99'}
    
    for label, size in zip(labels, sizes):
        if size > 0:
            filtered_labels.append(label)
            filtered_sizes.append(size)
            colors.append(color_map[label])
    
    if not filtered_sizes:
        return None
    
    explode = [0.05] * len(filtered_sizes)
    
    fig, ax = plt.subplots(figsize=(6, 6))
    
    wedges, texts, autotexts = ax.pie(filtered_sizes, 
                                      explode=explode,
                                      labels=filtered_labels,
                                      colors=colors,
                                      autopct='%1.1f%%',
                                      shadow=True,
                                      startangle=90,
                                      textprops={'fontsize': 10})
    
    ax.set_title('Распределение по кнопкам', fontsize=12, fontweight='bold', pad=20)
    
    plt.tight_layout()
    
    # Сохраняем в base64
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode('utf-8')
    
    return f"data:image/png;base64,{image_base64}"

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)