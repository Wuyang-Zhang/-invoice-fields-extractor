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
        self.current_folder = None
        self.selection_mode = 'image'

        container = tk.Frame(root, padx=16, pady=16)
        container.pack(fill='both', expand=True)

        title = tk.Label(container, text='Invoice OCR Parser', font=('Segoe UI', 16, 'bold'))
        title.pack(anchor='w')

        subtitle = tk.Label(
            container,
            text='Select one image or a folder of images to extract invoice number, issue date, tax amount, and total amount.',
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

        folder_button = tk.Button(controls, text='Select Folder', command=self.select_folder, width=14)
        folder_button.pack(side='left', padx=(0, 8))

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
        self.current_folder = None
        self.selection_mode = 'image'
        self.path_var.set(str(self.current_image))
        self.status_var.set('Image selected. Click Run Extraction.')

    def select_folder(self) -> None:
        folder_path = filedialog.askdirectory(
            title='Select image folder',
            initialdir=str(ROOT),
        )
        if not folder_path:
            return
        self.current_folder = Path(folder_path)
        self.current_image = None
        self.selection_mode = 'folder'
        self.path_var.set(str(self.current_folder))
        self.status_var.set('Folder selected. Click Run Extraction.')

    def run_extraction(self) -> None:
        if self.selection_mode == 'folder':
            if self.current_folder is None:
                messagebox.showwarning('Missing folder', 'Please select a folder first.')
                return
        else:
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
            if self.selection_mode == 'folder':
                results = self.extractor.extract_invoice_fields_from_directory(self.current_folder)
                payload = []
                for item in results:
                    payload.append(
                        {
                            'source_image': item.source_image,
                            'invoices': [invoice.__dict__ for invoice in item.invoices],
                            'error': item.error,
                        }
                    )
                self.status_var.set(f'Completed. Processed {len(payload)} image(s).')
            else:
                results = self.extractor.extract_invoice_fields(self.current_image)
                payload = [item.__dict__ for item in results]
                self.status_var.set(f'Completed. Detected {len(payload)} invoice(s).')
        except Exception as exc:
            self.status_var.set('Extraction failed')
            messagebox.showerror('Extraction failed', str(exc))
            return
        finally:
            self.root.config(cursor='')

        self.set_output(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    app_root = tk.Tk()
    InvoiceApp(app_root)
    app_root.mainloop()
