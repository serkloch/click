import tkinter as tk
from tkinter import messagebox, ttk
import json
import threading
import time
from datetime import datetime
import requests
from collections import defaultdict
import os
import sys
from pynput import mouse
from pynput.mouse import Listener as MouseListener
import logging
from queue import Queue

# Отключаем логгирование pynput
logging.getLogger('pynput').setLevel(logging.WARNING)

class GlobalClickCounterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Global Click Counter")
        self.root.geometry("450x550")
        
        # Иконка приложения
        try:
            self.root.iconbitmap('click_icon.ico')
        except:
            pass
        
        # Переменные
        self.is_counting = False
        self.start_time = None
        self.click_count = 0
        self.session_data = defaultdict(int)  # minute -> clicks
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Слушатель мыши
        self.mouse_listener = None
        
        # Очередь для безопасного обновления GUI из потоков
        self.click_queue = Queue()
        
        # Статистика по кнопкам мыши
        self.button_stats = {'left': 0, 'right': 0, 'middle': 0}
        
        # Интерфейс
        self.create_widgets()
        self.create_tray_icon()
        
        # Загрузка конфигурации
        self.load_config()
        
        # Запуск обработчика очереди
        self.process_queue()
        
        # Защита от случайного закрытия
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
    
    def create_widgets(self):
        # Стиль
        style = ttk.Style()
        style.configure("TButton", padding=6, font=("Arial", 10))
        style.configure("Title.TLabel", font=("Arial", 14, "bold"))
        
        # Фрейм заголовка
        header_frame = ttk.Frame(self.root, padding="10")
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        ttk.Label(header_frame, text="🌐 Глобальный счетчик кликов", 
                 style="Title.TLabel").pack()
        ttk.Label(header_frame, text="Считает клики по всему экрану в любой программе",
                 font=("Arial", 9)).pack()
        
        # Индикатор состояния
        self.status_var = tk.StringVar(value="⏸ Ожидание")
        self.status_label = ttk.Label(header_frame, textvariable=self.status_var,
                                     font=("Arial", 10, "bold"))
        self.status_label.pack(pady=5)
        
        # Фрейм статистики
        stats_frame = ttk.LabelFrame(self.root, text="📊 Статистика в реальном времени", padding="10")
        stats_frame.grid(row=1, column=0, padx=10, pady=5, sticky=(tk.W, tk.E))
        
        # Сетка для статистики
        self.time_label = ttk.Label(stats_frame, text="Время сессии: 00:00:00", font=("Arial", 10))
        self.time_label.grid(row=0, column=0, pady=3, sticky=tk.W)
        
        self.total_clicks_label = ttk.Label(stats_frame, text="Всего кликов: 0", font=("Arial", 10))
        self.total_clicks_label.grid(row=1, column=0, pady=3, sticky=tk.W)
        
        self.cpm_label = ttk.Label(stats_frame, text="Кликов в минуту: 0", font=("Arial", 10))
        self.cpm_label.grid(row=2, column=0, pady=3, sticky=tk.W)
        
        # Статистика по кнопкам
        ttk.Label(stats_frame, text="По кнопкам:", 
                 font=("Arial", 10)).grid(row=0, column=1, padx=(20,0))
        
        self.left_clicks_label = ttk.Label(stats_frame, text="ЛКМ: 0", font=("Arial", 9))
        self.left_clicks_label.grid(row=1, column=1, sticky=tk.W, padx=(20,0))
        
        self.right_clicks_label = ttk.Label(stats_frame, text="ПКМ: 0", font=("Arial", 9))
        self.right_clicks_label.grid(row=2, column=1, sticky=tk.W, padx=(20,0))
        
        # Фрейм управления
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.grid(row=2, column=0, sticky=(tk.W, tk.E))
        
        self.start_button = ttk.Button(control_frame, text="▶ Начать сессию", 
                                      command=self.start_session)
        self.start_button.grid(row=0, column=0, padx=5)
        
        self.stop_button = ttk.Button(control_frame, text="⏹ Завершить сессию", 
                                     command=self.stop_session, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=5)
        
        # Фрейм истории по минутам
        history_frame = ttk.LabelFrame(self.root, text="📈 Клики по минутам", padding="10")
        history_frame.grid(row=3, column=0, padx=10, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Скроллируемый текст для истории
        self.history_text = tk.Text(history_frame, height=6, width=50, font=("Consolas", 9))
        scrollbar = ttk.Scrollbar(history_frame, orient="vertical", command=self.history_text.yview)
        self.history_text.configure(yscrollcommand=scrollbar.set)
        
        self.history_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Фрейм настроек сервера
        server_frame = ttk.LabelFrame(self.root, text="⚙ Настройки сервера", padding="10")
        server_frame.grid(row=4, column=0, padx=10, pady=5, sticky=(tk.W, tk.E))
        
        ttk.Label(server_frame, text="URL сервера:").grid(row=0, column=0, sticky=tk.W)
        
        self.server_url = tk.StringVar(value="http://localhost:5000")
        self.url_entry = ttk.Entry(server_frame, textvariable=self.server_url, width=35)
        self.url_entry.grid(row=0, column=1, padx=5)
        
        ttk.Button(server_frame, text="Сохранить", 
                  command=self.save_config).grid(row=0, column=2)
        
        # Фрейм информации
        info_frame = ttk.Frame(self.root, padding="10")
        info_frame.grid(row=5, column=0, sticky=(tk.W, tk.E))
        
        ttk.Label(info_frame, text="💡 Данные автоматически отправляются на сервер при завершении сессии",
                 font=("Arial", 9)).pack()
        
        # Настройка растягивания
        self.root.columnconfigure(0, weight=1)
        stats_frame.columnconfigure(1, weight=1)
        history_frame.columnconfigure(0, weight=1)
        history_frame.rowconfigure(0, weight=1)
    
    def create_tray_icon(self):
        """Создание иконки в системном трее"""
        try:
            from pystray import Icon, Menu, MenuItem
            from PIL import Image, ImageDraw
            import threading as th
            
            # Создаем простую иконку
            def create_image():
                image = Image.new('RGB', (64, 64), color='white')
                draw = ImageDraw.Draw(image)
                draw.ellipse([10, 10, 54, 54], fill='blue', outline='black')
                draw.text((20, 22), "C", fill='white')
                return image
            
            self.tray_icon = None
            
            def setup_tray():
                image = create_image()
                menu = Menu(
                    MenuItem('Показать', self.show_window),
                    MenuItem('Скрыть', self.hide_window),
                    MenuItem('---', None),
                    MenuItem('Начать сессию', self.start_session),
                    MenuItem('Остановить сессию', self.stop_session),
                    MenuItem('---', None),
                    MenuItem('Выход', self.quit_app)
                )
                self.tray_icon = Icon("click_counter", image, "Click Counter", menu)
                self.tray_icon.run()
            
            # Запускаем трей в отдельном потоке
            self.tray_thread = th.Thread(target=setup_tray, daemon=True)
            self.tray_thread.start()
            
        except ImportError:
            # Если библиотеки не установлены, просто пропускаем трей
            pass
    
    def setup_mouse_listener(self):
        """Настройка слушателя мыши"""
        def on_click(x, y, button, pressed):
            if pressed and self.is_counting:
                # Определяем кнопку мыши
                btn_name = str(button).split('.')[-1]
                
                # Добавляем клик в очередь для безопасной обработки в главном потоке
                self.click_queue.put(('click', btn_name, time.time()))
        
        # Запускаем слушатель мыши в отдельном потоке
        self.mouse_listener = MouseListener(on_click=on_click)
        self.mouse_listener.start()
    
    def process_queue(self):
        """Обработка событий из очереди"""
        try:
            while not self.click_queue.empty():
                item = self.click_queue.get_nowait()
                if item[0] == 'click':
                    _, btn_name, click_time = item
                    self.handle_click(btn_name, click_time)
        except:
            pass
        
        # Планируем следующую проверку очереди
        self.root.after(100, self.process_queue)
    
    def handle_click(self, button_name, click_time):
        """Обработка клика мыши"""
        if not self.is_counting:
            return
        
        self.click_count += 1
        
        # Обновляем статистику по кнопкам
        if button_name == 'left':
            self.button_stats['left'] += 1
        elif button_name == 'right':
            self.button_stats['right'] += 1
        elif button_name == 'middle':
            self.button_stats['middle'] += 1
        
        # Определяем текущую минуту
        if self.start_time:
            current_minute = int((click_time - self.start_time) // 60)
            self.session_data[current_minute] += 1
        
        # Обновляем отображение
        self.update_display(click_time)
        
        # Обновляем историю каждые 10 кликов
        if self.click_count % 10 == 0:
            self.update_history()
    
    def start_session(self):
        """Начать новую сессию подсчета"""
        self.is_counting = True
        self.start_time = time.time()
        self.click_count = 0
        self.session_data.clear()
        self.button_stats = {'left': 0, 'right': 0, 'middle': 0}
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Обновляем интерфейс
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_var.set("▶ Счет активен")
        self.status_label.config(foreground="green")
        
        # Очищаем историю
        self.history_text.delete(1.0, tk.END)
        
        # Настраиваем слушатель мыши
        self.setup_mouse_listener()
        
        # Запускаем таймер обновления
        self.update_timer()
        
        # Показываем уведомление
        self.show_notification("Сессия начата", "Подсчет кликов активирован")
    
    def stop_session(self):
        """Завершить текущую сессию"""
        self.is_counting = False
        
        # Останавливаем слушателя мыши
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None
        
        # Обновляем интерфейс
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("⏹ Сессия завершена")
        self.status_label.config(foreground="red")
        
        # Сохранение данных сессии в файл
        self.save_session_to_file()
        
        # Обновляем историю
        self.update_history()
        
        # Автоматически отправляем данные на сервер
        self.auto_send_data()
        
        # Показываем уведомление
        self.show_notification("Сессия завершена", 
                             f"Всего кликов: {self.click_count}")
    
    def save_session_to_file(self):
        """Сохранение данных сессии в JSON файл"""
        session_data = {
            'session_id': self.session_id,
            'total_clicks': self.click_count,
            'start_time': self.start_time,
            'clicks_per_minute': dict(self.session_data),
            'button_stats': self.button_stats,
            'timestamp': datetime.now().isoformat()
        }
        
        # Создаем папку для сессий, если ее нет
        os.makedirs('sessions', exist_ok=True)
        
        filename = f"sessions/session_{self.session_id}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
        
        return filename
    
    def auto_send_data(self):
        """Автоматическая отправка данных на сервер"""
        if not self.session_data:
            return
        
        # Подготовка данных
        data = {
            'session_id': self.session_id,
            'total_clicks': self.click_count,
            'clicks_per_minute': dict(self.session_data),
            'button_stats': self.button_stats,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # Отправка на сервер
            response = requests.post(
                f"{self.server_url.get()}/api/session",
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                self.show_notification("Данные отправлены", 
                                     f"Сессия {self.session_id} сохранена на сервере")
                
                # Открываем браузер с графиком в отдельном потоке
                threading.Thread(target=self.open_browser_with_graph, 
                               args=(result.get('session_id'),), 
                               daemon=True).start()
            else:
                self.show_notification("Ошибка отправки", 
                                     f"Ошибка сервера: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            self.show_notification("Ошибка подключения", 
                                 "Не удалось подключиться к серверу")
            # Сохраняем данные для отправки позже
            self.save_for_later_send(data)
        except Exception as e:
            self.show_notification("Ошибка", f"Ошибка отправки: {str(e)}")
            self.save_for_later_send(data)
    
    def save_for_later_send(self, data):
        """Сохранить данные для отправки позже"""
        pending_file = f"sessions/pending_{self.session_id}.json"
        with open(pending_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Пытаемся отправить отложенные данные
        threading.Thread(target=self.send_pending_data, daemon=True).start()
    
    def send_pending_data(self):
        """Отправка отложенных данных"""
        pending_dir = 'sessions'
        for filename in os.listdir(pending_dir):
            if filename.startswith('pending_'):
                filepath = os.path.join(pending_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    response = requests.post(
                        f"{self.server_url.get()}/api/session",
                        json=data,
                        headers={'Content-Type': 'application/json'},
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        os.remove(filepath)
                        print(f"Отложенные данные {filename} успешно отправлены")
                except:
                    continue
    
    def open_browser_with_graph(self, session_id):
        """Открыть браузер с графиком"""
        try:
            import webbrowser
            webbrowser.open(f"{self.server_url.get()}/session/{session_id}")
        except:
            pass
    
    def update_display(self, current_time=None):
        """Обновление отображения статистики"""
        if not self.start_time:
            return
        
        elapsed_time = time.time() - self.start_time
        hours = int(elapsed_time // 3600)
        minutes = int((elapsed_time % 3600) // 60)
        seconds = int(elapsed_time % 60)
        
        self.time_label.config(text=f"Время сессии: {hours:02d}:{minutes:02d}:{seconds:02d}")
        self.total_clicks_label.config(text=f"Всего кликов: {self.click_count}")
        
        # Кликов в минуту
        current_minute = int(elapsed_time // 60) if elapsed_time > 0 else 0
        cpm = self.session_data.get(current_minute, 0)
        self.cpm_label.config(text=f"Кликов в минуту: {cpm}")
        
        # Обновляем статистику по кнопкам
        self.left_clicks_label.config(text=f"ЛКМ: {self.button_stats['left']}")
        self.right_clicks_label.config(text=f"ПКМ: {self.button_stats['right']}")
    
    def update_history(self):
        """Обновление истории кликов"""
        self.history_text.delete(1.0, tk.END)
        
        if not self.session_data:
            self.history_text.insert(tk.END, "Нет данных")
            return
        
        # Сортировка по минутам
        sorted_minutes = sorted(self.session_data.keys())
        
        # Заголовок
        self.history_text.insert(tk.END, "Минута | Кликов\n")
        self.history_text.insert(tk.END, "───────┼────────\n")
        
        for minute in sorted_minutes:
            clicks = self.session_data[minute]
            # Создаем простую гистограмму
            bar = "█" * min(clicks, 50)  # Ограничиваем длину бара
            self.history_text.insert(tk.END, f"{minute + 1:6d} │ {clicks:4d} {bar}\n")
    
    def update_timer(self):
        """Обновление таймера"""
        if self.is_counting:
            self.update_display()
            self.root.after(1000, self.update_timer)  # Обновлять каждую секунду
    
    def load_config(self):
        """Загрузка конфигурации из файла"""
        config_file = "global_click_counter_config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    self.server_url.set(config.get('server_url', 'http://localhost:5000'))
            except:
                pass
    
    def save_config(self):
        """Сохранение конфигурации в файл"""
        config = {'server_url': self.server_url.get()}
        with open('global_click_counter_config.json', 'w') as f:
            json.dump(config, f)
        messagebox.showinfo("Успех", "Настройки сохранены!")
    
    def show_notification(self, title, message):
        """Показ уведомления"""
        try:
            # Для Windows
            if sys.platform == 'win32':
                from win10toast import ToastNotifier
                toaster = ToastNotifier()
                toaster.show_toast(title, message, duration=3, threaded=True)
            # Для Linux с libnotify
            elif sys.platform.startswith('linux'):
                import subprocess
                subprocess.Popen(['notify-send', title, message])
            # Для macOS
            elif sys.platform == 'darwin':
                import subprocess
                subprocess.Popen(['osascript', '-e', 
                                 f'display notification "{message}" with title "{title}"'])
        except:
            # Если не удалось показать уведомление, просто обновляем статус
            self.status_var.set(f"{title}: {message}")
    
    def minimize_to_tray(self):
        """Свернуть в трей"""
        self.root.withdraw()
        self.show_notification("Счетчик кликов", "Приложение свернуто в трей")
    
    def show_window(self):
        """Показать окно"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
    
    def hide_window(self):
        """Скрыть окно"""
        self.root.withdraw()
    
    def quit_app(self):
        """Выход из приложения"""
        # Останавливаем слушателей
        if self.mouse_listener:
            self.mouse_listener.stop()
        
        # Останавливаем трей
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        
        # Выходим
        self.root.quit()
        self.root.destroy()
        sys.exit(0)

def main():
    root = tk.Tk()
    app = GlobalClickCounterApp(root)
    root.mainloop()

if __name__ == "__main__":
    # Проверка прав администратора (рекомендуется для глобальных хуков)
    if sys.platform == 'win32':
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            print("Запуск с правами администратора рекомендуется для глобального отслеживания кликов")
            print("Но можно попробовать и без них...")
    
    main()