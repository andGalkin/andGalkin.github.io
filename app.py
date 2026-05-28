import customtkinter as ctk
from tkinter import filedialog, messagebox
import sqlite3
import pandas as pd
import os
import sys
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
        if getattr(sys, 'frozen', False):
            # Если запущено как .exe
            self.db_name = os.path.join(os.path.dirname(sys.executable), "datamatrix.db")
        
        self.init_db()

        # Интерфейс
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Верхняя панель
        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        self.btn_load = ctk.CTkButton(self.top_frame, text="Загрузить CSV", command=self.load_csv)
        self.btn_load.pack(side="left", padx=5)

        self.btn_export = ctk.CTkButton(self.top_frame, text="Экспорт в CSV", command=self.export_csv)
        self.btn_export.pack(side="left", padx=5)

        self.lbl_status = ctk.CTkLabel(self.top_frame, text="Готов к работе")
        self.lbl_status.pack(side="right", padx=10)

        # Список кодов
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Список кодов")
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        self.refresh_list()

    def init_db(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE,
                description TEXT,
                status TEXT DEFAULT 'Активный',
                order_number TEXT,
                used_date TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def refresh_list(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
            
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT code, status, order_number, used_date FROM codes ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()

        header = ctk.CTkFrame(self.scroll_frame)
        header.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(header, text="Код", width=200, anchor="w").pack(side="left", padx=5)
        ctk.CTkLabel(header, text="Статус", width=100, anchor="w").pack(side="left", padx=5)
        ctk.CTkLabel(header, text="Заказ", width=150, anchor="w").pack(side="left", padx=5)
        ctk.CTkLabel(header, text="Дата использования", width=150, anchor="w").pack(side="left", padx=5)

        for row in rows:
            item_frame = ctk.CTkFrame(self.scroll_frame)
            item_frame.pack(fill="x", padx=5, pady=1)
            
            color = "green" if row[1] == 'Активный' else "red"
            
            ctk.CTkLabel(item_frame, text=row[0], width=200, anchor="w").pack(side="left", padx=5)
            ctk.CTkLabel(item_frame, text=row[1], text_color=color, width=100, anchor="w").pack(side="left", padx=5)
            ctk.CTkLabel(item_frame, text=row[2] or "-", width=150, anchor="w").pack(side="left", padx=5)
            ctk.CTkLabel(item_frame, text=row[3] or "-", width=150, anchor="w").pack(side="left", padx=5)

    def load_csv(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not file_path:
            return

        try:
            df = pd.read_csv(file_path)
            if df.shape[1] < 1:
                raise ValueError("Файл пуст или неверный формат")
            
            codes_col = df.columns[0]
            desc_col = df.columns[1] if df.shape[1] > 1 else None
            
            new_codes = []
            existing_active_codes = []

            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()

            for index, row in df.iterrows():
                code = str(row[codes_col]).strip()
                desc = str(row[desc_col]).strip() if desc_col is not None and pd.notna(row[desc_col]) else ""
                
                cursor.execute("SELECT status FROM codes WHERE code = ?", (code,))
                result = cursor.fetchone()
                
                if result:
                    if result[0] == 'Активный':
                        existing_active_codes.append(code)
                else:
                    new_codes.append((code, desc))

            if new_codes:
                cursor.executemany("INSERT OR IGNORE INTO codes (code, description) VALUES (?, ?)", new_codes)
            
            conn.commit()
            conn.close()

            msg = f"Новых кодов добавлено: {len(new_codes)}\n"
            
            if existing_active_codes:
                dialog = ctk.CTkToplevel(self)
                dialog.title("Обнаружены дубликаты")
                dialog.geometry("400x200")
                dialog.grab_set()
                
                ctk.CTkLabel(dialog, text=f"Найдено {len(existing_active_codes)} кодов (статус: Активный).\nВведите номер заказа:").pack(pady=10, padx=10)
                
                entry_order = ctk.CTkEntry(dialog, placeholder_text="Номер заказа")
                entry_order.pack(pady=10, padx=20, fill="x")
                
                def confirm_update():
                    order_num = entry_order.get().strip()
                    if not order_num:
                        messagebox.showwarning("Ошибка", "Введите номер заказа!")
                        return
                    
                    conn = sqlite3.connect(self.db_name)
                    cursor = conn.cursor()
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    placeholders = ','.join('?' * len(existing_active_codes))
                    sql = f"UPDATE codes SET status='Использован', order_number=?, used_date=? WHERE code IN ({placeholders})"
                    params = [order_num, now] + existing_active_codes
                    
                    cursor.execute(sql, params)
                    conn.commit()
                    conn.close()
                    
                    msg += f"Обновлено: {len(existing_active_codes)}\nЗаказ: {order_num}"
                    messagebox.showinfo("Результат", msg)
                    dialog.destroy()
                    self.refresh_list()

                ctk.CTkButton(dialog, text="Подтвердить", command=confirm_update).pack(pady=10)
            else:
                messagebox.showinfo("Результат", msg)
                self.refresh_list()

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить файл:\n{str(e)}")

    def export_csv(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not file_path:
            return
        
        try:
            conn = sqlite3.connect(self.db_name)
            df = pd.read_sql_query("SELECT code, description, status, order_number, used_date FROM codes", conn)
            conn.close()
            df.to_csv(file_path, index=False, sep=';')
            messagebox.showinfo("Успех", "Данные экспортированы!")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка экспорта: {str(e)}")

if __name__ == "__main__":
    app = DataMatrixApp()
    app.mainloop()
