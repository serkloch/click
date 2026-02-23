#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import threading
import time
from datetime import datetime
from collections import defaultdict
import os
import sys
from pynput import mouse
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np

# Настройка шрифтов matplotlib для кириллицы
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'DejaVu Sans', 'Liberation Sans', 'sans-serif']

class ClickAnalyticsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Click Analytics - Анализ кликов")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # Переменные для сбора кликов
        self.is_counting = False
        self.start_time = None
        self.click_count = 0
        self.session_data = defaultdict(int)  # minute -> clicks
        self.button_stats = {'left': 0, 'right': 0, 'middle': 0}
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.mouse_listener = None
        
        # Создаём папку для сессий
        os.makedirs('sessions', exist_ok=True)
        
        # Создаём интерфейс
        self.create_widgets()
        
        # Загружаем список сессий при запуске
        self.refresh_sessions_list()
        
        # Закрытие слушателя при выходе
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_widgets(self):
        # Основной контейнер с вкладками
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Вкладка 1: Сбор кликов
        self.tab_collect = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_collect, text="📊 Сбор кликов")
        self.create_collect_tab()
        
        # Вкладка 2: История и графики
        self.tab_history = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_history, text="📈 История сессий")
        self.create_history_tab()
        
        # Статус бар
        self.status_var = tk.StringVar(value="Готов к работе")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def create_collect_tab(self):
        # Верхняя панель с информацией
        info_frame = ttk.LabelFrame(self.tab_collect, text="Текущая сессия", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(info_frame, text="Статус:", font=('Arial', 10)).grid(row=0, column=0, sticky=tk.W, pady=2)
        self.status_label = ttk.Label(info_frame, text="⏸ Ожидание", font=('Arial', 10, 'bold'))
        self.status_label.grid(row=0, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(info_frame, text="Время сессии:", font=('Arial', 10)).grid(row=1, column=0, sticky=tk.W, pady=2)
        self.time_label = ttk.Label(info_frame, text="00:00:00", font=('Arial', 10, 'bold'))
        self.time_label.grid(row=1, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(info_frame, text="Всего кликов:", font=('Arial', 10)).grid(row=2, column=0, sticky=tk.W, pady=2)
        self.total_clicks_label = ttk.Label(info_frame, text="0", font=('Arial', 10, 'bold'))
        self.total_clicks_label.grid(row=2, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(info_frame, text="Кликов в минуту:", font=('Arial', 10)).grid(row=3, column=0, sticky=tk.W, pady=2)
        self.cpm_label = ttk.Label(info_frame, text="0", font=('Arial', 10, 'bold'))
        self.cpm_label.grid(row=3, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(info_frame, text="Кликов в секунду:", font=('Arial', 10)).grid(row=4, column=0, sticky=tk.W, pady=2)
        self.cps_label = ttk.Label(info_frame, text="0.0", font=('Arial', 10, 'bold'))
        self.cps_label.grid(row=4, column=1, sticky=tk.W, pady=2)
        
        # Статистика по кнопкам
        ttk.Label(info_frame, text="ЛКМ:", font=('Arial', 10)).grid(row=0, column=2, sticky=tk.W, padx=(20,0), pady=2)
        self.left_label = ttk.Label(info_frame, text="0", font=('Arial', 10, 'bold'))
        self.left_label.grid(row=0, column=3, sticky=tk.W, pady=2)
        
        ttk.Label(info_frame, text="ПКМ:", font=('Arial', 10)).grid(row=1, column=2, sticky=tk.W, padx=(20,0), pady=2)
        self.right_label = ttk.Label(info_frame, text="0", font=('Arial', 10, 'bold'))
        self.right_label.grid(row=1, column=3, sticky=tk.W, pady=2)
        
        ttk.Label(info_frame, text="СКМ:", font=('Arial', 10)).grid(row=2, column=2, sticky=tk.W, padx=(20,0), pady=2)
        self.middle_label = ttk.Label(info_frame, text="0", font=('Arial', 10, 'bold'))
        self.middle_label.grid(row=2, column=3, sticky=tk.W, pady=2)
        
        # Кнопки управления
        btn_frame = ttk.Frame(self.tab_collect)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.start_btn = ttk.Button(btn_frame, text="▶ Начать сессию", command=self.start_session, width=20)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(btn_frame, text="⏹ Завершить сессию", command=self.stop_session, state=tk.DISABLED, width=20)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        self.pause_btn = ttk.Button(btn_frame, text="⏸ Пауза", command=self.pause_session, state=tk.DISABLED, width=15)
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        
        self.save_btn = ttk.Button(btn_frame, text="💾 Сохранить сессию", command=self.save_session, state=tk.DISABLED, width=20)
        self.save_btn.pack(side=tk.LEFT, padx=5)
        
        # Текстовая область для истории кликов по минутам
        history_frame = ttk.LabelFrame(self.tab_collect, text="Клики по минутам", padding=10)
        history_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.history_text = tk.Text(history_frame, height=12, font=('Consolas', 10))
        scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.history_text.yview)
        self.history_text.configure(yscrollcommand=scrollbar.set)
        self.history_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Информация о горячих клавишах
        hotkey_frame = ttk.LabelFrame(self.tab_collect, text="Горячие клавиши", padding=5)
        hotkey_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(hotkey_frame, text="Ctrl+Alt+S - Старт/стоп сессии   |   Ctrl+Alt+P - Пауза/продолжить").pack()
    
    def create_history_tab(self):
        # Левая панель со списком сессий
        left_frame = ttk.Frame(self.tab_history)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(10,5), pady=10)
        
        ttk.Label(left_frame, text="Сохранённые сессии:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        
        # Список сессий с прокруткой
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.sessions_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, width=35, height=20)
        self.sessions_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.sessions_listbox.yview)
        
        self.sessions_listbox.bind('<<ListboxSelect>>', self.on_session_select)
        
        # Кнопка обновления списка
        refresh_btn = ttk.Button(left_frame, text="🔄 Обновить список", command=self.refresh_sessions_list)
        refresh_btn.pack(fill=tk.X, pady=5)
        
        # Правая панель с графиками и информацией
        right_frame = ttk.Frame(self.tab_history)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,10), pady=10)
        
        # Информация о выбранной сессии
        self.session_info_frame = ttk.LabelFrame(right_frame, text="Информация о сессии", padding=10)
        self.session_info_frame.pack(fill=tk.X, pady=(0,10))
        
        self.info_text = tk.Text(self.session_info_frame, height=4, font=('Arial', 10), wrap=tk.WORD, state=tk.DISABLED)
        self.info_text.pack(fill=tk.X)
        
        # Вкладки для графиков внутри правой панели
        graph_notebook = ttk.Notebook(right_frame)
        graph_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Вкладка с графиком кликов по минутам
        self.tab_graph = ttk.Frame(graph_notebook)
        graph_notebook.add(self.tab_graph, text="📊 Клики по минутам")
        
        # Вкладка с круговой диаграммой кнопок
        self.tab_pie = ttk.Frame(graph_notebook)
        graph_notebook.add(self.tab_pie, text="🥧 Распределение по кнопкам")
        
        # Вкладка с кумулятивным графиком
        self.tab_cum = ttk.Frame(graph_notebook)
        graph_notebook.add(self.tab_cum, text="📈 Накопительный")
        
        # Создаём фигуры для графиков
        self.fig_clicks = Figure(figsize=(5,3), dpi=100)
        self.ax_clicks = self.fig_clicks.add_subplot(111)
        self.canvas_clicks = FigureCanvasTkAgg(self.fig_clicks, master=self.tab_graph)
        self.canvas_clicks.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        self.fig_pie = Figure(figsize=(5,3), dpi=100)
        self.ax_pie = self.fig_pie.add_subplot(111)
        self.canvas_pie = FigureCanvasTkAgg(self.fig_pie, master=self.tab_pie)
        self.canvas_pie.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        self.fig_cum = Figure(figsize=(5,3), dpi=100)
        self.ax_cum = self.fig_cum.add_subplot(111)
        self.canvas_cum = FigureCanvasTkAgg(self.fig_cum, master=self.tab_cum)
        self.canvas_cum.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Кнопка экспорта
        export_btn = ttk.Button(right_frame, text="📥 Экспорт в CSV", command=self.export_session)
        export_btn.pack(pady=5)
    
    # ---------- Методы для сбора кликов ----------
    def start_session(self):
        if self.is_counting:
            return
        self.is_counting = True
        self.start_time = time.time()
        self.click_count = 0
        self.session_data.clear()
        self.button_stats = {'left': 0, 'right': 0, 'middle': 0}
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.NORMAL, text="⏸ Пауза")
        self.save_btn.config(state=tk.DISABLED)
        self.status_label.config(text="▶ Активен", foreground="green")
        
        self.history_text.delete(1.0, tk.END)
        self.update_display()
        
        # Запускаем слушатель мыши
        self.setup_mouse_listener()
        
        # Запускаем таймер обновления
        self.update_timer()
        
        self.status_var.set("Сессия начата")
    
    def stop_session(self):
        self.is_counting = False
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None
        
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.DISABLED)
        self.save_btn.config(state=tk.NORMAL)
        self.status_label.config(text="⏹ Завершена", foreground="red")
        
        # Сохраняем в файл автоматически
        self.save_session(auto=True)
        
        self.status_var.set("Сессия завершена")
    
    def pause_session(self):
        if self.is_counting:
            self.is_counting = False
            self.pause_btn.config(text="▶ Продолжить")
            self.status_label.config(text="⏸ Пауза", foreground="orange")
            if self.mouse_listener:
                self.mouse_listener.stop()
                self.mouse_listener = None
        else:
            self.is_counting = True
            self.pause_btn.config(text="⏸ Пауза")
            self.status_label.config(text="▶ Активен", foreground="green")
            self.setup_mouse_listener()
    
    def setup_mouse_listener(self):
        def on_click(x, y, button, pressed):
            if pressed and self.is_counting:
                # Определяем кнопку
                btn = str(button).split('.')[-1]
                if btn == 'left':
                    self.button_stats['left'] += 1
                elif btn == 'right':
                    self.button_stats['right'] += 1
                elif btn == 'middle':
                    self.button_stats['middle'] += 1
                
                self.click_count += 1
                if self.start_time:
                    minute = int((time.time() - self.start_time) // 60)
                    self.session_data[minute] += 1
                self.update_display()
        
        self.mouse_listener = mouse.Listener(on_click=on_click)
        self.mouse_listener.start()
    
    def update_display(self):
        if not self.start_time:
            return
        
        elapsed = time.time() - self.start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        self.time_label.config(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        
        self.total_clicks_label.config(text=str(self.click_count))
        
        current_minute = int(elapsed // 60)
        cpm = self.session_data.get(current_minute, 0)
        self.cpm_label.config(text=str(cpm))
        
        if elapsed > 0:
            cps = self.click_count / elapsed
            self.cps_label.config(text=f"{cps:.2f}")
        
        self.left_label.config(text=str(self.button_stats['left']))
        self.right_label.config(text=str(self.button_stats['right']))
        self.middle_label.config(text=str(self.button_stats['middle']))
        
        # Обновляем текстовую историю
        self.update_history_text()
    
    def update_history_text(self):
        self.history_text.delete(1.0, tk.END)
        if not self.session_data:
            return
        sorted_minutes = sorted(self.session_data.keys())
        for minute in sorted_minutes:
            clicks = self.session_data[minute]
            bar = "█" * min(clicks, 50)
            self.history_text.insert(tk.END, f"Мин {minute+1:2d}: {clicks:4d} {bar}\n")
        self.history_text.see(tk.END)
    
    def update_timer(self):
        if self.is_counting:
            self.update_display()
            self.root.after(1000, self.update_timer)
    
    def save_session(self, auto=False):
        data = {
            'session_id': self.session_id,
            'total_clicks': self.click_count,
            'start_time': self.start_time,
            'duration': time.time() - self.start_time if self.start_time else 0,
            'clicks_per_minute': dict(self.session_data),
            'button_stats': self.button_stats,
            'timestamp': datetime.now().isoformat()
        }
        filename = f"sessions/{self.session_id}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        if auto:
            self.status_var.set("Сессия автоматически сохранена")
        else:
            messagebox.showinfo("Сохранено", f"Сессия сохранена в файл:\n{filename}")
            self.save_btn.config(state=tk.DISABLED)
        
        # Обновляем список сессий
        self.refresh_sessions_list()
    
    # ---------- Методы для работы с историей ----------
    def refresh_sessions_list(self):
        self.sessions_listbox.delete(0, tk.END)
        sessions = []
        for filename in os.listdir('sessions'):
            if filename.endswith('.json'):
                try:
                    with open(f'sessions/{filename}', 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    sess_id = data.get('session_id', filename)
                    ts = data.get('timestamp', '')
                    if ts:
                        display = f"{ts[:16]} – {data.get('total_clicks',0)} кликов"
                    else:
                        display = f"{sess_id[:8]} – {data.get('total_clicks',0)} кликов"
                    sessions.append((ts, display, sess_id))
                except:
                    continue
        # Сортируем по времени (новые сверху)
        sessions.sort(reverse=True)
        for ts, display, sess_id in sessions:
            self.sessions_listbox.insert(tk.END, display)
            self.sessions_listbox.itemconfig(tk.END, {'tags': (sess_id,)})
    
    def on_session_select(self, event):
        selection = self.sessions_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        sess_id = self.sessions_listbox.itemcget(index, 'tags')[0]  # получаем тег с ID
        self.display_session(sess_id)
    
    def display_session(self, session_id):
        filename = f"sessions/{session_id}.json"
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            messagebox.showerror("Ошибка", "Не удалось загрузить сессию")
            return
        
        # Информация о сессии
        info = f"ID: {data.get('session_id')}\n"
        info += f"Дата: {data.get('timestamp', '')[:19]}\n"
        info += f"Всего кликов: {data.get('total_clicks', 0)}\n"
        info += f"Длительность: {data.get('duration', 0):.1f} сек\n"
        
        button_stats = data.get('button_stats', {})
        info += f"ЛКМ: {button_stats.get('left',0)}  ПКМ: {button_stats.get('right',0)}  СКМ: {button_stats.get('middle',0)}"
        
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, info)
        self.info_text.config(state=tk.DISABLED)
        
        # Построение графиков
        self.plot_clicks_per_minute(data)
        self.plot_button_pie(data)
        self.plot_cumulative(data)
    
    def plot_clicks_per_minute(self, data):
        clicks_data = data.get('clicks_per_minute', {})
        if not clicks_data:
            self.ax_clicks.clear()
            self.ax_clicks.text(0.5, 0.5, 'Нет данных по минутам', ha='center', va='center')
            self.canvas_clicks.draw()
            return
        
        minutes = sorted(int(k) for k in clicks_data.keys())
        values = [clicks_data[str(m)] for m in minutes]
        labels = [f"{m+1}" for m in minutes]
        
        self.ax_clicks.clear()
        bars = self.ax_clicks.bar(labels, values, color='skyblue', edgecolor='black')
        self.ax_clicks.set_xlabel('Минута')
        self.ax_clicks.set_ylabel('Кликов')
        self.ax_clicks.set_title('Клики по минутам')
        self.ax_clicks.grid(axis='y', alpha=0.3)
        
        # Добавляем подписи над столбцами
        for bar, v in zip(bars, values):
            height = bar.get_height()
            self.ax_clicks.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                            str(v), ha='center', va='bottom', fontsize=8)
        
        if len(labels) > 10:
            plt.setp(self.ax_clicks.xaxis.get_majorticklabels(), rotation=45)
        
        self.fig_clicks.tight_layout()
        self.canvas_clicks.draw()
    
    def plot_button_pie(self, data):
        button_stats = data.get('button_stats', {})
        left = button_stats.get('left', 0)
        right = button_stats.get('right', 0)
        middle = button_stats.get('middle', 0)
        total = left + right + middle
        
        if total == 0:
            self.ax_pie.clear()
            self.ax_pie.text(0.5, 0.5, 'Нет данных по кнопкам', ha='center', va='center')
            self.canvas_pie.draw()
            return
        
        sizes = [left, right, middle]
        labels = ['ЛКМ', 'ПКМ', 'СКМ']
        colors = ['#66b3ff', '#ff9999', '#99ff99']
        explode = (0.05, 0.05, 0.05)
        
        self.ax_pie.clear()
        self.ax_pie.pie(sizes, explode=explode, labels=labels, colors=colors,
                       autopct='%1.1f%%', shadow=True, startangle=90)
        self.ax_pie.set_title('Распределение по кнопкам мыши')
        self.canvas_pie.draw()
    
    def plot_cumulative(self, data):
        clicks_data = data.get('clicks_per_minute', {})
        if not clicks_data:
            self.ax_cum.clear()
            self.ax_cum.text(0.5, 0.5, 'Нет данных по минутам', ha='center', va='center')
            self.canvas_cum.draw()
            return
        
        minutes = sorted(int(k) for k in clicks_data.keys())
        values = [clicks_data[str(m)] for m in minutes]
        cumulative = np.cumsum(values)
        labels = [f"{m+1}" for m in minutes]
        
        self.ax_cum.clear()
        self.ax_cum.plot(labels, cumulative, marker='o', linestyle='-', color='green')
        self.ax_cum.fill_between(labels, cumulative, alpha=0.2)
        self.ax_cum.set_xlabel('Минута')
        self.ax_cum.set_ylabel('Накопительные клики')
        self.ax_cum.set_title('Кумулятивный график')
        self.ax_cum.grid(alpha=0.3)
        
        if len(labels) > 10:
            plt.setp(self.ax_cum.xaxis.get_majorticklabels(), rotation=45)
        
        self.fig_cum.tight_layout()
        self.canvas_cum.draw()
    
    def export_session(self):
        selection = self.sessions_listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите сессию для экспорта")
            return
        index = selection[0]
        sess_id = self.sessions_listbox.itemcget(index, 'tags')[0]
        filename = f"sessions/{sess_id}.json"
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            messagebox.showerror("Ошибка", "Не удалось загрузить сессию")
            return
        
        # Создаем CSV
        import csv
        from tkinter import filedialog
        file_path = filedialog.asksaveasfilename(defaultextension=".csv",
                                                  filetypes=[("CSV files", "*.csv")])
        if not file_path:
            return
        
        clicks_data = data.get('clicks_per_minute', {})
        minutes = sorted(int(k) for k in clicks_data.keys())
        
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Минута', 'Кликов'])
            for m in minutes:
                writer.writerow([m+1, clicks_data[str(m)]])
        
        messagebox.showinfo("Экспорт", "Данные экспортированы в CSV")
    
    def on_closing(self):
        if self.is_counting:
            if messagebox.askyesno("Выход", "Сессия ещё активна. Остановить и выйти?"):
                self.stop_session()
            else:
                return
        if self.mouse_listener:
            self.mouse_listener.stop()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = ClickAnalyticsApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()