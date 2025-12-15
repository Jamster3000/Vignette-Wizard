import customtkinter as ctk
import tkinter
from tkinter import colorchooser, filedialog
from PIL import Image, ImageDraw, ImageFilter, ImageTk
import numpy as np
import math
import os
import threading
import json
import time
from functools import wraps
import logging
import csv
from plyer import notification
import sys

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

DEBUG_MODE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("debug.log"),
    ] if DEBUG_MODE else []
)

timings = []

def log_execution_time(func):
    """Decorator to record each function call as a separate row in the CSV."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        logging.info("Function '%s' executed in %.4f seconds", func.__name__, execution_time)
        timings.append({
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'func_name': func.__name__,
            'execution_time': f"{execution_time:.4f}"
        })
        return result
    return wrapper

def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def create_circular_mask(size, radius, vignette_strength):
    """Create circular vignette mask with optimized NumPy operations."""
    width, height = size
    center_x = (width - 1) * 0.5
    center_y = (height - 1) * 0.5

    # Use meshgrid with float32 for faster computation
    x = np.arange(width, dtype=np.float32)
    y = np.arange(height, dtype=np.float32)
    X, Y = np.meshgrid(x, y)

    # Calculate distance from center using hypot (faster than manual sqrt)
    X -= center_x
    Y -= center_y
    dist = np.hypot(X, Y)

    # Calculate fade range
    corner_dist = math.hypot(center_x, center_y)
    
    # FIX: When vignette_strength is high, reduce fade_range dramatically
    # This creates a sharper edge at high strength values
    if vignette_strength >= 5.0:
        # At strength 10, fade_range becomes very small (sharp edge)
        strength_factor = (10.0 - vignette_strength) / 5.0  # 1.0 at strength=5, 0.0 at strength=10
        strength_factor = max(0.05, strength_factor)  # Minimum 5% fade range
        fade_range = (corner_dist - radius) * strength_factor
    else:
        fade_range = corner_dist - radius
    
    if fade_range <= 0:
        fade_range = corner_dist * 0.3

    # Vectorized mask calculation - minimize intermediate arrays
    # Compute (dist - radius), clamp to [0, fade_range], normalize, apply power
    np.maximum(dist, radius, out=dist)  # dist = max(dist, radius)
    dist -= radius  # dist = dist_beyond_radius
    dist *= (1.0 / fade_range)  # normalize
    np.minimum(dist, 1.0, out=dist)  # clamp to 1.0
    
    # Apply vignette strength and convert to mask
    np.power(dist, vignette_strength, out=dist)
    dist *= -255.0
    dist += 255.0
    mask = dist.astype(np.uint8)

    # Create image from array
    mask_image = Image.fromarray(mask, mode='L')

    # Single Gaussian blur pass (faster than double box blur)
    # Reduce blur for high strength values to maintain sharp edge
    blur_amount = max(1, int(fade_range // 25))
    if blur_amount > 1 and vignette_strength < 8.0:
        mask_image = mask_image.filter(ImageFilter.GaussianBlur(blur_amount))

    return mask_image

class AppState:
    """Application state and global configuration variables"""
    def __init__(self):
        self.chosen_color = "#000000"
        self.label_complete = None
        self.processing = False
        self.debug_mode = False
        self.stop_processing = False

class VignetteApp:
    SETTINGS_FILE = "vignette_settings.json"
    DEFAULT_SETTINGS = {
        "vignette_strength": "2.5",
        "diagonal_radius": "4.0",
        "vignette_color": "#000000",
        "spinbox_step": "1"
    }

    def __init__(self):
        self.state = AppState()
        self.window = None
        self.frame = None
        self.widgets = {}
        self.setup_ui()

    def load_settings(self):
        """Load settings from JSON file"""
        try:
            if os.path.exists(self.SETTINGS_FILE):
                with open(self.SETTINGS_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading settings: {e}")
        return self.DEFAULT_SETTINGS.copy()

    def save_settings(self):
        """Save current settings to JSON file."""
        try:
            settings = {
                "vignette_strength": self.widgets['vignette_strength_value'].get(),
                "diagonal_radius": self.widgets['diagonal_radius_value'].get(),
                "vignette_color": self.state.chosen_color,
                "spinbox_step": self.widgets['spinbox_value'].get()
            }
            with open(self.SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def reset_to_defaults(self):
        """Reset all settings to default values."""
        self.widgets['vignette_strength_value'].set(self.DEFAULT_SETTINGS["vignette_strength"])
        self.widgets['diagonal_radius_value'].set(self.DEFAULT_SETTINGS["diagonal_radius"])
        self.widgets['spinbox_value'].set(self.DEFAULT_SETTINGS["spinbox_step"])
        self.state.chosen_color = self.DEFAULT_SETTINGS["vignette_color"]
        self.widgets['soft_edge_color'].configure(fg_color=self.state.chosen_color)

    @log_execution_time
    def add_debug_overlay(self, result, width, height, vignette_strength, diagonal_radius):
        """Add debug visualization overlay to the image."""
        from PIL import ImageFont
        draw = ImageDraw.Draw(result)

        center_x = (width - 1) / 2.0
        center_y = (height - 1) / 2.0
        diagonal = math.sqrt(width**2 + height**2)
        actual_radius = int(diagonal / diagonal_radius)
        corner_dist = math.sqrt(center_x**2 + center_y**2)

        fade_range = corner_dist - actual_radius
        if fade_range <= 0:
            fade_range = corner_dist * 0.3

        base_size = min(width, height)
        font_size = max(14, base_size // 35)
        small_font_size = max(12, base_size // 40)

        try:
            font = ImageFont.truetype("arial.ttf", font_size)
            small_font = ImageFont.truetype("arial.ttf", small_font_size)
            title_font = ImageFont.truetype("arialbd.ttf", font_size + 2)
        except:
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size)
                small_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", small_font_size)
                title_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", font_size + 2)
            except:
                font = ImageFont.load_default()
                small_font = font
                title_font = font

        if actual_radius > 0:
            bbox = [center_x - actual_radius, center_y - actual_radius, center_x + actual_radius, center_y + actual_radius]
            draw.ellipse(bbox, outline="#00FF00", width=4)
            label_text = f"CLEAR ZONE: {actual_radius}px"
            text_x = center_x - 60
            text_y = int(center_y - actual_radius - small_font_size - 5)
            if text_y > 5:
                draw.rectangle([text_x - 2, text_y - 1, text_x + 130, text_y + small_font_size + 1], fill="#000000")
                draw.text((text_x, text_y), label_text, fill="#00FF00", font=small_font)

        fade_thresholds = [
            (0.25, "#FFFF00", "25% fade"),
            (0.50, "#FF8800", "50% fade"),
            (0.75, "#FF0000", "75% fade"),
            (1.0, "#FF00FF", "100% fade"),
        ]

        for fade_pct, color, label in fade_thresholds:
            norm_fade = fade_pct ** (1 / vignette_strength)
            actual_dist = actual_radius + (norm_fade * fade_range)

            if actual_dist > 0 and actual_dist < max(width, height):
                bbox = [center_x - actual_dist, center_y - actual_dist, center_x + actual_dist, center_y + actual_dist]
                draw.ellipse(bbox, outline=color, width=2)

        crosshair_size = max(30, base_size // 20)
        draw.line([(center_x - crosshair_size, center_y), (center_x + crosshair_size, center_y)], fill="#00FFFF", width=2)
        draw.line([(center_x, center_y - crosshair_size), (center_x, center_y + crosshair_size)], fill="#00FFFF", width=2)
        draw.ellipse([center_x - 4, center_y - 4, center_x + 4, center_y + 4], fill="#00FFFF")

        edge_points = [(0, center_y), (width - 1, center_y), (center_x, 0), (center_x, height - 1)]
        for ex, ey in edge_points:
            draw.line([(center_x, center_y), (ex, ey)], fill="#00FFFF", width=1)

        corner_markers = [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]
        for cx, cy in corner_markers:
            m = 12
            if cx == 0:
                draw.line([(cx, cy), (cx + m, cy)], fill="#FFFFFF", width=2)
            else:
                draw.line([(cx, cy), (cx - m, cy)], fill="#FFFFFF", width=2)
            if cy == 0:
                draw.line([(cx, cy), (cx, cy + m)], fill="#FFFFFF", width=2)
            else:
                draw.line([(cx, cy), (cx, cy - m)], fill="#FFFFFF", width=2)

        true_center_x = (width - 1) / 2.0
        true_center_y = (height - 1) / 2.0
        tl_dist = int(math.sqrt((0 - true_center_x)**2 + (0 - true_center_y)**2))
        tr_dist = int(math.sqrt((width - 1 - true_center_x)**2 + (0 - true_center_y)**2))
        bl_dist = int(math.sqrt((0 - true_center_x)**2 + (height - 1 - true_center_y)**2))
        br_dist = int(math.sqrt((width - 1 - true_center_x)**2 + (height - 1 - true_center_y)**2))

        line_height = small_font_size + 6
        info_lines = [
            ("DEBUG MODE", "#FF4444", title_font),
            ("", None, None),
            (f"Size: {width}x{height}", "#FFFFFF", small_font),
            (f"Diagonal: {int(diagonal)}px", "#FFFFFF", small_font),
            ("", None, None),
            ("Settings:", "#00FFFF", small_font),
            (f"Strength: {vignette_strength:.1f}", "#FFFF00", small_font),
            (f"Radius Divisor: {diagonal_radius:.1f}", "#FFFF00", small_font),
            ("", None, None),
            ("Zones:", "#00FFFF", small_font),
            (f"Clear Zone: {actual_radius}px", "#00FF00", small_font),
            (f"Fade Range: {int(fade_range)}px", "#FF8800", small_font),
            (f"Corner Dist: {int(corner_dist)}px", "#FFFFFF", small_font),
            ("", None, None),
            ("Legend:", "#00FFFF", small_font),
            ("GREEN = Clear zone edge", "#00FF00", small_font),
            ("YELLOW = 25% darkened", "#FFFF00", small_font),
            ("ORANGE = 50% darkened", "#FF8800", small_font),
            ("RED = 75% darkened", "#FF0000", small_font),
            ("MAGENTA = 100% darkened", "#FF00FF", small_font),
            ("", None, None),
            ("Corners:", "#00FFFF", small_font),
            (f"TL: {tl_dist}px  TR: {tr_dist}px", "#FFFFFF", small_font),
            (f"BL: {bl_dist}px  BR: {br_dist}px", "#FFFFFF", small_font),
        ]

        panel_width = 450
        panel_height = len(info_lines) * line_height + 15
        panel_x = 8
        panel_y = 8
        
        # Use NumPy for fast panel darkening instead of pixel-by-pixel loop
        panel_x2 = min(panel_x + panel_width, width)
        panel_y2 = min(panel_y + panel_height, height)
        panel_region = result.crop((panel_x, panel_y, panel_x2, panel_y2))
        panel_array = np.array(panel_region, dtype=np.uint8)
        panel_array = panel_array // 3  # Darken by dividing by 3
        darkened_panel = Image.fromarray(panel_array)
        result.paste(darkened_panel, (panel_x, panel_y))
        
        draw = ImageDraw.Draw(result)
        draw.rectangle([panel_x, panel_y, panel_x + panel_width, panel_y + panel_height], outline="#666666", width=1)
        y_offset = panel_y + 8
        for line_text, color, line_font in info_lines:
            if line_text and color:
                draw.text((panel_x + 8, y_offset), line_text, fill=color, font=line_font)
            y_offset += line_height
        return result

    def process_images(self, path, step):
        """Process all images in the specified path sequentially."""
        global timings
        timings.clear()

        try:
            progress_bar = ctk.CTkProgressBar(master=self.frame, width=400, height=20, fg_color=("#FF0000", "#B22222"), progress_color=("#32CD32", "#006400"), mode="determinate")
            progress_bar.set(0)
            progress_bar.place(relx=0.5, rely=0.84, anchor='center')

            # Filter for actual image files only
            valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp', '.gif'}
            files = sorted([f for f in os.listdir(path) 
                           if os.path.splitext(f)[1].lower() in valid_extensions])
            files_to_process = [f for i, f in enumerate(files) if i % step == 0]
            total_files = len(files_to_process)

            if total_files == 0:
                progress_bar.destroy()
                return

            # Get settings once
            vignette_strength = float(self.widgets['vignette_strength_value'].get())
            diagonal_radius = float(self.widgets['diagonal_radius_value'].get())
            chosen_color = self.state.chosen_color
            is_debug = self.state.debug_mode

            processed = 0
            failed = 0
            stopped = False

            # Process images sequentially
            for img_name in files_to_process:
                if self.state.stop_processing:
                    stopped = True
                    break

                # Process single image
                overall_start = time.time()
                try:
                    full_path = os.path.join(path, img_name)
                    
                    # Open image and get dimensions in one step
                    with Image.open(full_path) as img:
                        img = img.convert("RGB")
                        width, height = img.size
                        
                        # Use hypot for faster diagonal calculation
                        diagonal = math.hypot(width, height)
                        radius = int(diagonal / diagonal_radius)
                        strength = max(0.1, min(10.0, vignette_strength))

                        # Time the mask creation
                        start_time = time.time()
                        vignette = create_circular_mask((width, height), radius, strength)
                        end_time = time.time()
                        timings.append({
                            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                            'func_name': 'create_circular_mask',
                            'execution_time': f"{end_time - start_time:.4f}"
                        })

                        # Create background color
                        color_rgb = (0, 255, 0) if is_debug else hex_to_rgb(chosen_color)
                        colored_bg = Image.new("RGB", (width, height), color_rgb)

                        # Composite images
                        result = Image.composite(img, colored_bg, vignette)

                    # Time image save operation
                    start_time = time.time()
                    output_folder = 'processed_debug' if is_debug else 'processed'
                    output_path = os.path.join(path, output_folder)
                    os.makedirs(output_path, exist_ok=True)
                    
                    # Optimize save based on format
                    save_path = os.path.join(output_path, img_name)
                    ext = os.path.splitext(img_name)[1].lower()
                    if ext in ('.jpg', '.jpeg'):
                        result.save(save_path, quality=95, optimize=False, subsampling=0)
                    elif ext == '.png':
                        result.save(save_path, compress_level=1)  # Fast compression
                    else:
                        result.save(save_path)
                        
                    end_time = time.time()
                    timings.append({
                        'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                        'func_name': 'save_image',
                        'execution_time': f"{end_time - start_time:.4f}"
                    })

                    # Record overall processing time
                    overall_end = time.time()
                    timings.append({
                        'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                        'func_name': 'process_image',
                        'execution_time': f"{overall_end - overall_start:.4f}"
                    })

                    processed += 1
                except Exception as e:
                    logging.error(f"Error processing {img_name}: {e}")
                    overall_end = time.time()
                    timings.append({
                        'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                        'func_name': 'process_image',
                        'execution_time': f"{overall_end - overall_start:.4f}"
                    })
                    failed += 1

                # Update progress for every image
                progress = (processed + failed) / total_files
                progress_bar.set(progress)
                self.window.update()  # Update UI to show progress

            progress_bar.destroy()

            if self.state.label_complete:
                self.state.label_complete.destroy()

            if stopped:
                self.state.label_complete = ctk.CTkLabel(master=self.frame, text='Processing stopped by user', font=("Helvetica", 13, "bold"), text_color="#FF9999")
                self.state.stop_processing = False
            else:
                msg = f'All images completed! ({processed} processed, {failed} failed)' if failed > 0 else 'All images completed!'
                self.state.label_complete = ctk.CTkLabel(master=self.frame, text=msg, font=("Helvetica", 13, "bold"), text_color="#00FF00")
                self._write_timing_to_csv()
                # Send notification
                notification.notify(
                    title='Vignette Wizard',
                    message=msg,
                    timeout=5,
                    app_icon=resource_path("icon.ico"),
                )

            self.state.label_complete.place(relx=0.5, rely=0.92, anchor='center')
            self.state.label_complete.update()

            self.state.processing = False
            self.widgets['continue_button'].configure(state='normal')
            self.window.deiconify()
            self.window.after_idle(self.window.attributes, '-topmost', False)

        except FileNotFoundError:
            if 'progress_bar' in locals():
                progress_bar.destroy()
            error_label = ctk.CTkLabel(master=self.frame, text='Incorrect path name\n\nCheck your path name and try again.', bg_color="#e0e0e0")
            error_label.place(relx=0.5, rely=0.7, anchor='center')
            error_label.update()
            self.widgets['continue_button'].configure(state='normal')
            self.state.processing = False

    def handle_keypress(self, event=None):
        """Handle start processing button press."""
        if self.state.processing:
            return

        if self.state.label_complete:
            self.state.label_complete.destroy()

        self.widgets['continue_button'].configure(state='disabled')
        self.state.processing = True

        threading.Thread(target=self.process_images, args=(self.widgets['entry_path'].get(), int(self.widgets['spinbox_value'].get()))).start()

    def handle_esc_key(self, event=None):
        """Handle ESC key to stop processing."""
        if self.state.processing:
            self.state.stop_processing = True
            self.state.processing = False
            self.widgets['continue_button'].configure(state='normal')

    def choose_color(self):
        """Open color chooser dialog."""
        color = colorchooser.askcolor(title="Choose color for soft edge")[1]
        if color:
            self.state.chosen_color = color
            self.widgets['soft_edge_color'].configure(fg_color=self.state.chosen_color)

    def choose_folder(self):
        """Open folder picker dialog."""
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.widgets['entry_path'].delete(0, tkinter.END)
            self.widgets['entry_path'].insert(0, folder_selected)

    def toggle_debug_mode(self):
        """Toggle debug mode."""
        self.state.debug_mode = self.widgets['debug_checkbox_var'].get()

    def on_closing(self):
        """Handle window closing."""
        self.save_settings()
        self.window.destroy()

    def setup_ui(self):
        """Setup the user interface."""
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        saved_settings = self.load_settings()
        self.state.chosen_color = saved_settings.get("vignette_color", "#000000")

        self.window = ctk.CTk()
        self.window.geometry("500x680")
        self.window.resizable(False, False)
        self.window.title("Vignette Wizard - Image Processor")

        try:
            ico_path = resource_path("icon.ico")
            if os.path.exists(ico_path):
                self.window.iconbitmap(ico_path)
            else:
                png_path = resource_path("icon.png")
                if os.path.exists(png_path):
                    ico = Image.open(png_path)
                    photo = ImageTk.PhotoImage(ico)
                    self.window.iconphoto(True, photo)
        except Exception as e:
            print(f"Could not set window icon: {e}")

        self.frame = ctk.CTkFrame(master=self.window, width=500, height=680)
        self.frame.pack(pady=10, padx=10, fill="both", expand=True)

        path_label = ctk.CTkLabel(master=self.frame, text='Please input path to images')
        path_label.place(relx=0.5, rely=0.05, anchor='center')
        path_label.configure(font=("Helvetica", 16, "bold"))

        self.widgets['entry_path'] = ctk.CTkEntry(master=self.frame, width=350, height=35, placeholder_text="Enter folder path or use button below...")
        self.widgets['entry_path'].place(relx=0.5, rely=0.10, anchor='center')
        self.widgets['entry_path'].bind('<Return>', self.handle_keypress)

        folder_picker_button = ctk.CTkButton(master=self.frame, text="Choose Folder", command=self.choose_folder, width=200, height=32)
        folder_picker_button.place(relx=0.5, rely=0.16, anchor='center')

        spinbox_label = ctk.CTkLabel(master=self.frame, text='Step interval (process every Nth image):')
        spinbox_label.place(relx=0.5, rely=0.22, anchor='center')
        spinbox_label.configure(font=("Helvetica", 13))

        spinbox_frame = ctk.CTkFrame(master=self.frame, fg_color="transparent")
        spinbox_frame.place(relx=0.5, rely=0.27, anchor='center')

        self.widgets['spinbox_value'] = ctk.StringVar(value=saved_settings.get("spinbox_step", "1"))

        spinbox = ctk.CTkEntry(master=spinbox_frame, width=60, textvariable=self.widgets['spinbox_value'], justify="center")
        spinbox.grid(row=0, column=1, padx=5)

        spinbox_decrement_button = ctk.CTkButton(master=spinbox_frame, text='-', width=40, height=32, command=self._decrement_spinbox)
        spinbox_decrement_button.grid(row=0, column=0, padx=5)

        spinbox_increment_button = ctk.CTkButton(master=spinbox_frame, text='+', width=40, height=32, command=self._increment_spinbox)
        spinbox_increment_button.grid(row=0, column=2, padx=5)

        vignette_strength_label = ctk.CTkLabel(master=self.frame, text='Vignette Strength:')
        vignette_strength_label.place(relx=0.5, rely=0.34, anchor='center')
        vignette_strength_label.configure(font=("Helvetica", 13))

        vignette_strength_frame = ctk.CTkFrame(master=self.frame, fg_color="transparent")
        vignette_strength_frame.place(relx=0.5, rely=0.39, anchor='center')

        self.widgets['vignette_strength_value'] = ctk.StringVar(value=saved_settings.get("vignette_strength", "2.5"))

        vignette_strength_spinbox = ctk.CTkEntry(master=vignette_strength_frame, width=60, textvariable=self.widgets['vignette_strength_value'], justify="center")
        vignette_strength_spinbox.grid(row=0, column=1, padx=5)

        vignette_strength_decrement_button = ctk.CTkButton(master=vignette_strength_frame, text='-', width=40, height=32, command=self._decrement_vignette_strength)
        vignette_strength_decrement_button.grid(row=0, column=0, padx=5)

        vignette_strength_increment_button = ctk.CTkButton(master=vignette_strength_frame, text='+', width=40, height=32, command=self._increment_vignette_strength)
        vignette_strength_increment_button.grid(row=0, column=2, padx=5)

        diagonal_radius_label = ctk.CTkLabel(master=self.frame, text='Radius Divisor (larger = smaller clear zone):')
        diagonal_radius_label.place(relx=0.5, rely=0.46, anchor='center')
        diagonal_radius_label.configure(font=("Helvetica", 13))

        diagonal_radius_frame = ctk.CTkFrame(master=self.frame, fg_color="transparent")
        diagonal_radius_frame.place(relx=0.5, rely=0.51, anchor='center')

        self.widgets['diagonal_radius_value'] = ctk.StringVar(value=saved_settings.get("diagonal_radius", "4.0"))

        diagonal_radius_spinbox = ctk.CTkEntry(master=diagonal_radius_frame, width=60, textvariable=self.widgets['diagonal_radius_value'], justify="center")
        diagonal_radius_spinbox.grid(row=0, column=1, padx=5)

        diagonal_radius_decrement_button = ctk.CTkButton(master=diagonal_radius_frame, text='-', width=40, height=32, command=self._decrement_diagonal_radius)
        diagonal_radius_decrement_button.grid(row=0, column=0, padx=5)

        diagonal_radius_increment_button = ctk.CTkButton(master=diagonal_radius_frame, text='+', width=40, height=32, command=self._increment_diagonal_radius)
        diagonal_radius_increment_button.grid(row=0, column=2, padx=5)

        soft_edge_color_label = ctk.CTkLabel(master=self.frame, text="Vignette Color (click to change):")
        soft_edge_color_label.place(relx=0.5, rely=0.58, anchor='center')
        soft_edge_color_label.configure(font=("Helvetica", 13))

        self.widgets['soft_edge_color'] = ctk.CTkButton(master=self.frame, text='', command=self.choose_color, fg_color=self.state.chosen_color, hover_color=self.state.chosen_color, width=50, height=30, corner_radius=5, border_width=2, border_color="#666666")
        self.widgets['soft_edge_color'].place(anchor='center', relx=0.5, rely=0.63)

        reset_button = ctk.CTkButton(master=self.frame, text='Reset', command=self.reset_to_defaults, width=60, height=24, font=("Helvetica", 10))
        reset_button.place(relx=0.87, rely=0.63, anchor='center')

        self.widgets['debug_checkbox_var'] = ctk.BooleanVar(value=False)
        debug_checkbox = ctk.CTkCheckBox(
            master=self.frame,
            text="Debug Mode (green vignette + markers)",
            variable=self.widgets['debug_checkbox_var'],
            command=self.toggle_debug_mode,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            checkmark_color="#FFFFFF",
            font=("Helvetica", 12)
        )
        debug_checkbox.place(relx=0.5, rely=0.70, anchor='center')

        self.widgets['continue_button'] = ctk.CTkButton(master=self.frame, text='Process Images', command=self.handle_keypress, width=180, height=40, font=("Helvetica", 14, "bold"))
        self.widgets['continue_button'].place(anchor='center', relx=0.5, rely=0.78)

        self.window.bind('<Escape>', self.handle_esc_key)
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _increment_spinbox(self):
        """Increment spinbox value."""
        current_value = int(self.widgets['spinbox_value'].get())
        self.widgets['spinbox_value'].set(str(current_value + 1))

    def _decrement_spinbox(self):
        """Decrement spinbox value."""
        current_value = int(self.widgets['spinbox_value'].get())
        if current_value > 1:
            self.widgets['spinbox_value'].set(str(current_value - 1))

    def _increment_vignette_strength(self):
        """Increment vignette strength."""
        try:
            current_value = float(self.widgets['vignette_strength_value'].get())
            self.widgets['vignette_strength_value'].set(f"{current_value + 0.1:.1f}")
        except ValueError:
            self.widgets['vignette_strength_value'].set("2.5")

    def _decrement_vignette_strength(self):
        """Decrement vignette strength."""
        try:
            current_value = float(self.widgets['vignette_strength_value'].get())
            if current_value > 0.0:
                self.widgets['vignette_strength_value'].set(f"{current_value - 0.1:.1f}")
        except ValueError:
            self.widgets['vignette_strength_value'].set("2.5")

    def _increment_diagonal_radius(self):
        """Increment diagonal radius."""
        try:
            current_value = float(self.widgets['diagonal_radius_value'].get())
            self.widgets['diagonal_radius_value'].set(f"{current_value + 1:.1f}")
        except ValueError:
            self.widgets['diagonal_radius_value'].set("4.0")

    def _decrement_diagonal_radius(self):
        """Decrement diagonal radius."""
        try:
            current_value = float(self.widgets['diagonal_radius_value'].get())
            if current_value > 1:
                self.widgets['diagonal_radius_value'].set(f"{current_value - 1:.1f}")
        except ValueError:
            self.widgets['diagonal_radius_value'].set("4.0")

    def run(self):
        """Run the application."""
        self.window.mainloop()

    def _write_timing_to_csv(self):
        """Write each function call as a row in the CSV."""
        global timings

        if not DEBUG_MODE or not timings:
            timings.clear()
            return

        csv_file = "timing_log.csv"

        existing_headers = []
        existing_rows = []
        if os.path.isfile(csv_file):
            with open(csv_file, mode='r', newline='') as f:
                reader = list(csv.reader(f))
                if reader:
                    existing_headers = reader[0]
                    existing_rows = reader[1:]

        all_function_names = sorted(set(list(existing_headers[1:]) + [t['func_name'] for t in timings]))
        headers = ["Timestamp"] + all_function_names

        new_rows = []
        for timing in timings:
            row = [timing['timestamp']]
            for func_name in all_function_names:
                if timing['func_name'] == func_name:
                    row.append(timing['execution_time'])
                else:
                    row.append('')
            new_rows.append(row)

        try:
            with open(csv_file, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(existing_rows)
                writer.writerows(new_rows)
            timings.clear()
        except Exception as e:
            logging.error(f"Error writing timing CSV: {e}")

if __name__ == "__main__":
    app = VignetteApp()
    app.run()