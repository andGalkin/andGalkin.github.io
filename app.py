import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import csv
import sqlite3
import os
import customtkinter as ctk
from datetime import datetime

# Настройки внешнего вида
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class DataMatrixApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Учёт Data Matrix кодов")
        self.geometry("900x600")

        # Инициализация БД
        self.db_name = "datamatrix.db"
        self.init_db()

        # Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Боковая панель
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="DM Учёт", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.btn_upload = ctk.CTkButton(self.sidebar_frame, text="Загрузить CSV", command=self.upload_csv)
        self.btn_upload.grid(row=1, column=0, padx=20, pady=10)

        self.btn_export = ctk.CTkButton(self.sidebar_frame, text="Экспорт в CSV", command=self.export_csv)
        self.btn_export.grid(row=2, column=0, padx=20, pady=10)

        self.btn_clear = ctk.CTkButton(self.sidebar_frame, text="Очистить базу", fg_color="red", command=self.clear_db)
        self.btn_clear.grid(row=3, column=0, padx=20, pady=10)

        self.status_label = ctk.CTkLabel(self.sidebar_frame, text="", wraplength=180)
        self.status_label.grid(row=5, column=0, padx=20, pady=20)

        # Основная область
        self.search_entry = ctk.CTkEntry(self, placeholder_text="Поиск по коду...")
        self.search_entry.grid(row=0, column=1, padx=20, pady=(20, 10), sticky="ew")
        self.search_entry.bind("<KeyRelease>", self.filter_table)

        # Таблица
        self.tree = ttk.Treeview(self, columns=("code", "description", "status", "order_id", "date_used"), show="headings")
        self.tree.heading("code", text="Код")
        self.tree.heading("description", text="Описание")
        self.tree.heading("status", text="Статус")
        self.tree.heading("order_id", text="№ Заказа")
        self.tree.heading("date_used", text="Дата использования")
        
        self.tree.column("code", width=250)
        self.tree.column("description", width=200)
        self.tree.column("status", width=100)
        self.tree.column("order_id", width=100)
        self.tree.column("date_used", width=150)

        self.tree.grid(row=1, column=1, padx=20, pady=10, sticky="nsew")

        # Scrollbar
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=2, sticky="ns", pady=10)

        self.load_data()

    def init_db(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE,
                description TEXT,
                status TEXT DEFAULT 'Активный',
                order_id TEXT,
                date_used TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def load_data(self, filter_text=""):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        query = "SELECT code, description, status, order_id, date_used FROM codes"
        if filter_text:
            query += f" WHERE code LIKE '%{filter_text}%'"
            
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            self.tree.insert("", tk.END, values=row)
        
        self.update_status(f"Всего записей: {len(rows)}")

    def update_status(self, text):
        self.status_label.configure(text=text)

    def upload_csv(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                # Пробуем определить разделитель
                sample = f.read(1024)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=';,')
                    reader = csv.reader(f, dialect)
                except:
                    reader = csv.reader(f, delimiter=';') # По умолчанию точка с запятой

                rows = list(reader)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось прочитать файл: {e}")
            return

        if not rows:
            messagebox.showwarning("Внимание", "Файл пуст")
            return

        # Разделяем на новые и существующие
        new_codes = []
        existing_codes = []

        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        for row in rows:
            if len(row) < 1: continue
            code = row[0].strip()
            desc = row[1].strip() if len(row) > 1 else ""
            
            if not code: continue

            # Проверка наличия
            cursor.execute("SELECT id, status FROM codes WHERE code=?", (code,))
            result = cursor.fetchone()

            if result:
                # Код существует
                db_id, status = result
                if status == 'Активный':
                    existing_codes.append((db_id, code))
                # Если уже использован, игнорируем или можно обновить описание (пока игнорируем)
            else:
                new_codes.append((code, desc))

        conn.close()

        # 1. Добавляем новые
        if new_codes:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            for code, desc in new_codes:
                try:
                    cursor.execute("INSERT INTO codes (code, description) VALUES (?, ?)", (code, desc))
                except sqlite3.IntegrityError:
                    pass # Дубликат в рамках одного файла
            conn.commit()
            conn.close()

        # 2. Обрабатываем существующие (Активные -> Использованные)
        if existing_codes:
            dialog = OrderDialog(self, len(existing_codes))
            self.wait_window(dialog)
            
            if dialog.result:
                order_id = dialog.result
                conn = sqlite3.connect(self.db_name)
                cursor = conn.cursor()
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                ids = [item[0] for item in existing_codes]
                placeholders = ','.join('?' * len(ids))
                
                cursor.execute(f"""
                    UPDATE codes 
                    SET status='Использован', order_id=?, date_used=? 
                    WHERE id IN ({placeholders})
                """, [order_id, now] + ids)
                
                conn.commit()
                conn.close()
                messagebox.showinfo("Успех", f"Обновлено статусов: {len(existing_codes)}\nЗаказ: {order_id}")
            else:
                messagebox.showinfo("Отмена", "Операция обновления статусов отменена пользователем.")

        elif not new_codes and not existing_codes:
             messagebox.showinfo("Инфо", "В файле не найдено новых или активных кодов для обработки.")
        else:
            if new_codes:
                messagebox.showinfo("Успех", f"Добавлено новых кодов: {len(new_codes)}")

        self.load_data()

    def export_csv(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not file_path:
            return
        
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT code, description, status, order_id, date_used FROM codes")
        rows = cursor.fetchall()
        conn.close()

        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(['Код', 'Описание', 'Статус', 'Заказ', 'Дата использования'])
                writer.writerows(rows)
            messagebox.showinfo("Успех", "Данные экспортированы!")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить файл: {e}")

    def filter_table(self, event):
        text = self.search_entry.get()
        self.load_data(text)

    def clear_db(self):
        if messagebox.askyesno("Подтверждение", "Вы уверены? Все данные будут удалены!"):
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM codes")
            conn.commit()
            conn.close()
            self.load_data()

class OrderDialog(ctk.CTkToplevel):
    def __init__(self, parent, count):
        super().__init__(parent)
        self.title("Ввод номера заказа")
        self.geometry("400x200")
        self.resizable(False, False)
        
        self.result = None

        label = ctk.CTkLabel(self, text=f"Найдено {count} совпадений.\nВведите номер заказа для списания:", font=ctk.CTkFont(size=14))
        label.pack(pady=20)

        self.entry = ctk.CTkEntry(self, width=300, placeholder_text="Например: ZAK-12345")
        self.entry.pack(pady=10)
        self.entry.focus()

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20)

        btn_ok = ctk.CTkButton(btn_frame, text="Применить", command=self.on_ok)
        btn_ok.pack(side=tk.LEFT, padx=10)

        btn_cancel = ctk.CTkButton(btn_frame, text="Отмена", fg_color="gray", command=self.destroy)
        btn_cancel.pack(side=tk.LEFT, padx=10)
        
        self.bind("<Return>", lambda e: self.on_ok())

    def on_ok(self):
        val = self.entry.get().strip()
        if val:
            self.result = val
            self.destroy()
        else:
            messagebox.showwarning("Внимание", "Номер заказа не может быть пустым!")

if __name__ == "__main__":
    app = DataMatrixApp()
    app.mainloop()