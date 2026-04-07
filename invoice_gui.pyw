from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

ROOT = Path(__file__).resolve().parent
SCRIPT_PATH = ROOT / '11.py'


def load_extractor():
    spec = importlib.util.spec_from_file_location('invoice_extractor_cli', SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Unable to load {SCRIPT_PATH}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class InvoiceApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title('Invoice OCR Parser')
        self.root.geometry('760x560')
        self.root.minsize(680, 480)

        self.extractor = load_extractor()
        self.current_image = None

        container = tk.Frame(root, padx=16, pady=16)
        container.pack(fill='both', expand=True)

        title = tk.Label(container, text='Invoice OCR Parser', font=('Segoe UI', 16, 'bold'))
        title.pack(anchor='w')

        subtitle = tk.Label(
            container,
            text='Select an image like 1.jpg to extract invoice number, issue date, tax amount, and total amount.',
            font=('Segoe UI', 10),
            justify='left',
            wraplength=720,
        )
        subtitle.pack(anchor='w', pady=(6, 12))

        controls = tk.Frame(container)
        controls.pack(fill='x', pady=(0, 12))

        self.path_var = tk.StringVar(value='No image selected')
        path_label = tk.Label(controls, textvariable=self.path_var, anchor='w')
        path_label.pack(side='left', fill='x', expand=True)

        open_button = tk.Button(controls, text='Select Image', command=self.select_image, width=14)
        open_button.pack(side='left', padx=(12, 8))

        run_button = tk.Button(controls, text='Run Extraction', command=self.run_extraction, width=14)
        run_button.pack(side='left')

        self.status_var = tk.StringVar(value='Ready')
        status = tk.Label(container, textvariable=self.status_var, anchor='w', fg='#444444')
        status.pack(fill='x', pady=(0, 8))

        self.output = scrolledtext.ScrolledText(container, font=('Consolas', 11), wrap='word')
        self.output.pack(fill='both', expand=True)
        self.output.insert('1.0', 'Results will appear here.\n')
        self.output.configure(state='disabled')

    def set_output(self, text: str) -> None:
        self.output.configure(state='normal')
        self.output.delete('1.0', 'end')
        self.output.insert('1.0', text)
        self.output.configure(state='disabled')

    def select_image(self) -> None:
        file_path = filedialog.askopenfilename(
            title='Select invoice image',
            filetypes=[('Image Files', '*.jpg *.jpeg *.png *.bmp'), ('All Files', '*.*')],
            initialdir=str(ROOT),
        )
        if not file_path:
            return
        self.current_image = Path(file_path)
        self.path_var.set(str(self.current_image))
        self.status_var.set('Image selected. Click Run Extraction.')

    def run_extraction(self) -> None:
        if self.current_image is None:
            default_image = ROOT / '1.jpg'
            if default_image.exists():
                self.current_image = default_image
                self.path_var.set(str(self.current_image))
            else:
                messagebox.showwarning('Missing image', 'Please select an image first.')
                return

        self.root.config(cursor='watch')
        self.root.update_idletasks()
        self.status_var.set('Running OCR...')

        try:
            results = self.extractor.extract_invoice_fields(self.current_image)
        except Exception as exc:
            self.status_var.set('Extraction failed')
            messagebox.showerror('Extraction failed', str(exc))
            return
        finally:
            self.root.config(cursor='')

        payload = [item.__dict__ for item in results]
        self.set_output(json.dumps(payload, ensure_ascii=False, indent=2))
        self.status_var.set(f'Completed. Detected {len(payload)} invoice(s).')


if __name__ == '__main__':
    app_root = tk.Tk()
    InvoiceApp(app_root)
    app_root.mainloop()
