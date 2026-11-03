import os
import threading
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import filedialog, scrolledtext
from processor import process_pdf


class PDFUploaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF to Asana Automation")
        self.root.geometry("760x560")
        self.file_path = None

        tb.Label(root, text="PDF to Asana Automation", font=("Segoe UI", 16, "bold")).pack(pady=10)

        self.file_label = tb.Label(root, text="No PDF selected", bootstyle="secondary")
        self.file_label.pack(pady=5)

        tb.Button(root, text="Select PDF", command=self.select_file, bootstyle="info").pack(pady=5)

        self.run_button = tb.Button(root, text="Run", command=self.run_process, bootstyle="success")
        self.run_button.pack(pady=10)

        self.status_label = tb.Label(root, text="Idle", bootstyle="secondary")
        self.status_label.pack(pady=5)

        self.progress = tb.Progressbar(root, bootstyle="success-striped", length=500, mode="determinate")
        self.progress.pack(pady=10)

        self.console = scrolledtext.ScrolledText(root, height=20, wrap="word")
        self.console.pack(fill="both", expand=True, padx=10, pady=10)

    def select_file(self):
        file = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if file:
            self.file_path = file
            self.file_label.config(text=os.path.basename(file))
            self.log(f"Selected: {file}")

    def log(self, message):
        self.console.insert("end", message + "\n")
        self.console.see("end")
        self.root.update_idletasks()

    def update_progress(self, value, message=""):
        self.progress["value"] = value
        self.status_label.config(text=message if message else "Working")
        if message:
            self.log(f"[{value}%] {message}")
        self.root.update_idletasks()

    def run_process(self):
        if not self.file_path:
            self.log("Please select a PDF first.")
            return

        self.run_button.config(state="disabled")
        self.progress["value"] = 0
        self.console.delete("1.0", "end")

        threading.Thread(target=self.worker, daemon=True).start()

    def worker(self):
        try:
            result = process_pdf(
                self.file_path,
                progress_callback=self.update_progress,
                log_callback=self.log,
            )

            self.log("")
            self.log("SUCCESS")
            self.log(f"Saved file: {result['file_saved']}")
            self.log(f"Items found: {result['items_all_count']}")
            self.log(f"Unique items: {result['items_unique_count']}")
            self.log(f"Processing time: {result['processing_seconds']} s")
            self.log("Tasks created:")

            for task in result["tasks_created"]:
                self.log(f" - {task['name']} | GID: {task['gid']}")

        except Exception as e:
            self.log(f"ERROR: {e}")
            self.status_label.config(text="Error")
            self.progress["value"] = 0
        finally:
            self.run_button.config(state="normal")


if __name__ == "__main__":
    app = tb.Window(themename="cosmo")
    PDFUploaderApp(app)
    app.mainloop()