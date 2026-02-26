#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Единое приложение для подсчёта и анализа кликов мыши.
Работает полностью оффлайн, не требует веб-сервера.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import time
from datetime import datetime
from collections import defaultdict
import threading
import sys

# Для глобального отслеживания кликов
try:
    from pynput import mouse
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    print("Предупреждение: pynput не установлен. Глобальное отслеживание кликов недоступно.")

# Для графиков
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

class Session:
    """Класс для хранения данных одной сессии."""
    def __init__(self, session_id=None):
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.start_time = None
        self.end_time = None
        self.total_clicks = 0
        self.clicks_per_minute = defaultdict(int)  # минута -> количество кликов
        self.button_stats = {'left': 0, 'right': 0, 'middle': 0}
    
    def to_dict(self):
        return {
            'session_id': self.session_id,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'total_clicks': self.total_clicks,
            'clicks_per_minute': dict(self.clicks_per_minute),
            'button_stats': self.button_stats,
            'timestamp': datetime.now().isoformat()
        }
    
    def from_dict(self, data):
        self.session_id = data.get('session_id', self.session_id)
        self.start_time = data.get('start_time')
        self.end_time = data.get('end_time')
        self.total_clicks = data.get('total_clicks', 0)
        self.clicks_per_minute = defaultdict(int, data.get('clicks_per_minute', {}))
        self.button_stats = data.get('button_stats', {'left':0, 'right':0, 'middle':0})
        return self

class ClickCounterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Click Counter & Analyzer")
        self.root.geometry("500x650")  # немного увеличил высоту для новой статистики
        self.root.resizable(False, False)
        
        # Переменные сессии
        self.current_session = Session()
        self.is_counting = False
        self.mouse_listener = None
        
        # Список сохранённых сессий и папка для них
        self.sessions_list = []
        self.sessions_dir = "sessions"
        os.makedirs(self.sessions_dir, exist_ok=True)
        
        # Загружаем список существующих сессий
        self.load_sessions_list()
        
        # Интерфейс
        self.create_widgets()
        
        # Запуск обработчика обновления времени
        self.update_clock()
        
        # Закрытие приложения
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_widgets(self):
        # Заголовок
        header_frame = ttk.Frame(self.root, padding="10")
        header_frame.pack(fill=tk.X)
        
        ttk.Label(header_frame, text="🖱️ Click Counter & Analyzer",
                 font=("Arial", 16, "bold")).pack()
        ttk.Label(header_frame, text="Счётчик кликов с анализом активности",
                 font=("Arial", 10)).pack()
        
        # Индикатор состояния
        self.status_var = tk.StringVar(value="⏸ Ожидание")
        self.status_label = ttk.Label(header_frame, textvariable=self.status_var,
                                     font=("Arial", 10, "bold"))
        self.status_label.pack(pady=5)
        
        # Основная область с вкладками
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Вкладка "Текущая сессия"
        self.session_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.session_tab, text="Текущая сессия")
        self.create_session_tab()
        
        # Вкладка "История сессий"
        self.history_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.history_tab, text="История")
        self.create_history_tab()
    
    def create_session_tab(self):
        # Статистика текущей сессии
        stats_frame = ttk.LabelFrame(self.session_tab, text="Статистика", padding="10")
        stats_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.time_label = ttk.Label(stats_frame, text="Время сессии: 00:00", font=("Arial", 11))
        self.time_label.grid(row=0, column=0, pady=5, sticky=tk.W)
        
        self.total_label = ttk.Label(stats_frame, text="Всего кликов: 0", font=("Arial", 11))
        self.total_label.grid(row=1, column=0, pady=5, sticky=tk.W)
        
        self.cpm_label = ttk.Label(stats_frame, text="Кликов в минуту: 0", font=("Arial", 11))
        self.cpm_label.grid(row=2, column=0, pady=5, sticky=tk.W)
        
        self.cps_label = ttk.Label(stats_frame, text="Кликов в секунду: 0.0", font=("Arial", 11))
        self.cps_label.grid(row=3, column=0, pady=5, sticky=tk.W)
        
        # Статистика по кнопкам мыши
        buttons_frame = ttk.LabelFrame(self.session_tab, text="По кнопкам", padding="10")
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Создаём три метки для каждой кнопки
        button_row = ttk.Frame(buttons_frame)
        button_row.pack(fill=tk.X)
        
        # Левая кнопка
        left_frame = ttk.Frame(button_row)
        left_frame.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        ttk.Label(left_frame, text="🖱️ Левая", font=("Arial", 10)).pack()
        self.left_label = ttk.Label(left_frame, text="0", font=("Arial", 12, "bold"), foreground="#2ecc71")
        self.left_label.pack()
        
        # Правая кнопка
        right_frame = ttk.Frame(button_row)
        right_frame.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        ttk.Label(right_frame, text="🖱️ Правая", font=("Arial", 10)).pack()
        self.right_label = ttk.Label(right_frame, text="0", font=("Arial", 12, "bold"), foreground="#e74c3c")
        self.right_label.pack()
        
        # Средняя кнопка
        middle_frame = ttk.Frame(button_row)
        middle_frame.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        ttk.Label(middle_frame, text="🖱️ Средняя", font=("Arial", 10)).pack()
        self.middle_label = ttk.Label(middle_frame, text="0", font=("Arial", 12, "bold"), foreground="#f39c12")
        self.middle_label.pack()
        
        # Кнопки управления
        control_frame = ttk.Frame(self.session_tab)
        control_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.start_btn = ttk.Button(control_frame, text="▶ Начать сессию",
                                   command=self.start_session)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(control_frame, text="⏹ Завершить сессию",
                                  command=self.stop_session, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        self.pause_btn = ttk.Button(control_frame, text="⏸ Пауза",
                                   command=self.pause_session, state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        
        self.stats_btn = ttk.Button(control_frame, text="📊 Показать график",
                                   command=self.show_current_session_graph,
                                   state=tk.DISABLED)
        self.stats_btn.pack(side=tk.LEFT, padx=5)
        
        # Текстовое поле для истории кликов по минутам
        history_frame = ttk.LabelFrame(self.session_tab, text="Клики по минутам", padding="10")
        history_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.history_text = tk.Text(history_frame, height=8, width=60, font=("Consolas", 9))
        scrollbar = ttk.Scrollbar(history_frame, orient="vertical", command=self.history_text.yview)
        self.history_text.configure(yscrollcommand=scrollbar.set)
        
        self.history_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def create_history_tab(self):
        # Список сохранённых сессий
        list_frame = ttk.Frame(self.history_tab)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Заголовок
        ttk.Label(list_frame, text="Сохранённые сессии", font=("Arial", 12, "bold")).pack(anchor=tk.W)
        
        # Рамка с прокруткой для списка
        canvas = tk.Canvas(list_frame, borderwidth=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Контейнер для кнопок сессий
        self.sessions_frame = scrollable_frame
        
        # Кнопка обновления списка
        ttk.Button(list_frame, text="🔄 Обновить список", command=self.refresh_sessions_list).pack(pady=5)
        
        # Первоначальное заполнение
        self.refresh_sessions_list()
    
    def refresh_sessions_list(self):
        # Очистить предыдущие виджеты
        for widget in self.sessions_frame.winfo_children():
            widget.destroy()
        
        self.load_sessions_list()
        
        if not self.sessions_list:
            ttk.Label(self.sessions_frame, text="Нет сохранённых сессий",
                     font=("Arial", 10)).pack(pady=20)
            return
        
        for sess_data in self.sessions_list:
            frame = ttk.Frame(self.sessions_frame, relief=tk.RAISED, borderwidth=1)
            frame.pack(fill=tk.X, pady=2, padx=5)
            
            # Информация о сессии
            info = f"{sess_data['timestamp'][:19]} | Кликов: {sess_data['total_clicks']} | Длит: {sess_data.get('duration', 0)} мин"
            ttk.Label(frame, text=info).pack(side=tk.LEFT, padx=5, pady=5)
            
            # Кнопка просмотра графика
            ttk.Button(frame, text="📊 График",
                      command=lambda sid=sess_data['id']: self.show_session_graph(sid)).pack(side=tk.RIGHT, padx=5)
    
    def load_sessions_list(self):
        """Загружает список сессий из папки sessions."""
        self.sessions_list = []
        if not os.path.exists(self.sessions_dir):
            return
        for filename in os.listdir(self.sessions_dir):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(self.sessions_dir, filename), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        clicks_data = data.get('clicks_per_minute', {})
                        duration = len(clicks_data)
                        self.sessions_list.append({
                            'id': data.get('session_id', filename),
                            'timestamp': data.get('timestamp', ''),
                            'total_clicks': data.get('total_clicks', 0),
                            'duration': duration,
                            'data': data
                        })
                except:
                    continue
        # Сортировка по убыванию времени
        self.sessions_list.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    def start_session(self):
        if self.is_counting:
            return
        self.is_counting = True
        self.current_session = Session()
        self.current_session.start_time = time.time()
        
        # Обновление интерфейса
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.NORMAL, text="⏸ Пауза")
        self.stats_btn.config(state=tk.DISABLED)
        self.status_var.set("▶ Счёт активен")
        
        # Очистка текстового поля истории
        self.history_text.delete(1.0, tk.END)
        
        # Сброс счётчиков кнопок на 0
        self.left_label.config(text="0")
        self.right_label.config(text="0")
        self.middle_label.config(text="0")
        
        # Запуск слушателя мыши, если доступно
        if PYNPUT_AVAILABLE:
            self.mouse_listener = mouse.Listener(on_click=self.on_click)
            self.mouse_listener.start()
        else:
            messagebox.showwarning("Предупреждение", "Библиотека pynput не установлена. Клики не будут отслеживаться глобально.")
    
    def stop_session(self):
        if not self.is_counting:
            return
        self.is_counting = False
        self.current_session.end_time = time.time()
        
        # Остановка слушателя
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None
        
        # Сохранение сессии
        self.save_current_session()
        
        # Обновление интерфейса
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.DISABLED, text="⏸ Пауза")
        self.stats_btn.config(state=tk.NORMAL)
        self.status_var.set("⏹ Сессия завершена")
        
        # Обновление истории кликов
        self.update_history_display()
        
        # Предложение показать график
        if messagebox.askyesno("Сессия завершена", "Показать график этой сессии?"):
            self.show_session_graph(self.current_session.session_id)
    
    def pause_session(self):
        if self.is_counting:
            self.is_counting = False
            self.pause_btn.config(text="▶ Продолжить")
            self.status_var.set("⏸ На паузе")
            if self.mouse_listener:
                self.mouse_listener.stop()
                self.mouse_listener = None
        else:
            self.is_counting = True
            self.pause_btn.config(text="⏸ Пауза")
            self.status_var.set("▶ Счёт активен")
            if PYNPUT_AVAILABLE:
                self.mouse_listener = mouse.Listener(on_click=self.on_click)
                self.mouse_listener.start()
    
    def on_click(self, x, y, button, pressed):
        if pressed and self.is_counting:
            # Определение кнопки
            btn_name = str(button).split('.')[-1]
            self.current_session.total_clicks += 1
            # Статистика по кнопкам
            if btn_name in self.current_session.button_stats:
                self.current_session.button_stats[btn_name] += 1
            # Клики по минутам
            current_minute = int((time.time() - self.current_session.start_time) // 60)
            self.current_session.clicks_per_minute[current_minute] += 1
            # Обновление интерфейса (выполняется в главном потоке через after)
            self.root.after(0, self.update_display)
    
    def update_display(self):
        if not self.current_session.start_time:
            return
        elapsed = time.time() - self.current_session.start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        self.time_label.config(text=f"Время сессии: {minutes:02d}:{seconds:02d}")
        self.total_label.config(text=f"Всего кликов: {self.current_session.total_clicks}")
        # Текущая минута
        current_minute = minutes
        cpm = self.current_session.clicks_per_minute.get(current_minute, 0)
        self.cpm_label.config(text=f"Кликов в минуту: {cpm}")
        # Кликов в секунду
        if elapsed > 0:
            cps = self.current_session.total_clicks / elapsed
            self.cps_label.config(text=f"Кликов в секунду: {cps:.2f}")
        
        # Обновление статистики по кнопкам
        self.left_label.config(text=str(self.current_session.button_stats.get('left', 0)))
        self.right_label.config(text=str(self.current_session.button_stats.get('right', 0)))
        self.middle_label.config(text=str(self.current_session.button_stats.get('middle', 0)))
    
    def update_clock(self):
        if self.is_counting:
            self.update_display()
        self.root.after(1000, self.update_clock)
    
    def update_history_display(self):
        self.history_text.delete(1.0, tk.END)
        if not self.current_session.clicks_per_minute:
            self.history_text.insert(tk.END, "Нет данных")
            return
        sorted_minutes = sorted(self.current_session.clicks_per_minute.keys())
        for minute in sorted_minutes:
            clicks = self.current_session.clicks_per_minute[minute]
            bar = "█" * min(clicks, 50)
            self.history_text.insert(tk.END, f"Минута {minute+1:2d}: {clicks:3d} {bar}\n")
    
    def save_current_session(self):
        """Сохраняет текущую сессию в JSON файл."""
        filename = os.path.join(self.sessions_dir, f"{self.current_session.session_id}.json")
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.current_session.to_dict(), f, ensure_ascii=False, indent=2)
        # Обновить список сессий на вкладке истории
        self.refresh_sessions_list()
    
    def show_current_session_graph(self):
        self.show_session_graph(self.current_session.session_id)
    
    def show_session_graph(self, session_id):
        """Открывает окно с графиком для указанной сессии."""
        # Загружаем данные сессии
        filename = os.path.join(self.sessions_dir, f"{session_id}.json")
        if not os.path.exists(filename):
            messagebox.showerror("Ошибка", "Файл сессии не найден")
            return
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Создаём окно графика
        graph_win = tk.Toplevel(self.root)
        graph_win.title(f"Анализ сессии {session_id[:8]}...")
        graph_win.geometry("800x600")
        graph_win.minsize(600, 400)
        
        # Верхняя панель с общей информацией
        info_frame = ttk.Frame(graph_win)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        total_clicks = data.get('total_clicks', 0)
        button_stats = data.get('button_stats', {})
        
        # Информация о сессии
        info_text = f"Всего кликов: {total_clicks}  |  "
        info_text += f"ЛКМ: {button_stats.get('left', 0)}  |  "
        info_text += f"ПКМ: {button_stats.get('right', 0)}  |  "
        info_text += f"СКМ: {button_stats.get('middle', 0)}"
        ttk.Label(info_frame, text=info_text, font=("Arial", 10)).pack()
        
        # Фрейм для графика
        fig = Figure(figsize=(8, 5), dpi=100)
        ax = fig.add_subplot(111)
        
        # Данные для графика
        clicks_data = data.get('clicks_per_minute', {})
        if not clicks_data:
            ttk.Label(graph_win, text="Нет данных по минутам").pack(pady=20)
            return
        
        minutes = sorted([int(k) for k in clicks_data.keys()])
        clicks = [clicks_data[str(m)] for m in minutes]
        x_labels = [f"{m+1}" for m in minutes]
        
        # Столбчатая диаграмма
        bars = ax.bar(x_labels, clicks, color='#3498db', edgecolor='white')
        ax.set_title(f"Клики по минутам (сессия {session_id[:8]}...)", fontsize=12)
        ax.set_xlabel("Минута")
        ax.set_ylabel("Количество кликов")
        ax.grid(axis='y', alpha=0.3)
        
        # Добавление значений над столбцами
        for bar, click in zip(bars, clicks):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                    f'{click}', ha='center', va='bottom', fontsize=8)
        
        # Встраивание графика в Tkinter
        canvas = FigureCanvasTkAgg(fig, master=graph_win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Статистика внизу
        stats_frame = ttk.Frame(graph_win)
        stats_frame.pack(fill=tk.X, padx=10, pady=10)
        
        duration = len(clicks_data)
        avg_cpm = total_clicks / duration if duration > 0 else 0
        max_cpm = max(clicks) if clicks else 0
        
        ttk.Label(stats_frame, text=f"Среднее в минуту: {avg_cpm:.1f}").pack(side=tk.LEFT, padx=10)
        ttk.Label(stats_frame, text=f"Максимум в минуту: {max_cpm}").pack(side=tk.LEFT, padx=10)
        
        # Кнопка закрытия
        ttk.Button(graph_win, text="Закрыть", command=graph_win.destroy).pack(pady=5)
    
    def on_closing(self):
        if self.is_counting:
            if messagebox.askyesno("Подтверждение", "Сессия ещё не завершена. Завершить сейчас?"):
                self.stop_session()
            else:
                return
        self.root.destroy()

def main():
    root = tk.Tk()
    app = ClickCounterApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()