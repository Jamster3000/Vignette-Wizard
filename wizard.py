'''
import customtkinter as ctk
import tkinter
from tkinter import colorchooser, filedialog
from PIL import Image, ImageDraw, ImageFilter, ImageTk
import numpy as np
import math
import os, time
import threading

chosen_color = "#000000"
label_complete = None
processing = False  # Track if processing is already ongoing

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

#@lru_cache(maxsize=None)
def create_circular_mask(size, radius, vignette_strength):
    width, height = size
    Y, X = np.ogrid[:height, :width]
    center_x, center_y = width // 2, height // 2

    # Calculate the distance of each pixel from the center
    dist = np.sqrt((X - center_x)**2 + (Y - center_y)**2)

    # Normalize the distance
    max_dist = np.sqrt(center_x**2 + center_y**2)
    norm_dist = dist / max_dist

    # Create the mask using a radial gradient
    mask = 255 * (1 - norm_dist**vignette_strength)
    mask = np.clip(mask, 0, 255).astype('uint8')

    # Convert numpy array to PIL Image
    mask_image = Image.fromarray(mask, mode='L')

    # Apply a slight Gaussian blur for smoother edges
    mask_image = mask_image.filter(ImageFilter.GaussianBlur(radius=radius // 30))

    return mask_image

def edit_image(path, image, vignette_strength=1.9, diagonal_radius=3):
    try:
        global chosen_color
        path = path + "\\"
        img = Image.open(path + image).convert("RGB")
        chosen_color_rgb = hex_to_rgb(chosen_color)

        # Calculate size
        width, height = img.size
        diagonal = math.sqrt(width**2 + height**2)
        radius = int(diagonal / diagonal_radius)

        vignette_strength = max(0.1, min(2.0, vignette_strength))

        # Create circular mask
        vignette = create_circular_mask((width, height), radius, vignette_strength)

        # Create a background with the chosen color
        colored_bg = Image.new("RGB", img.size, chosen_color_rgb)

        # Blend the original image with the colored background using the vignette mask
        result = Image.composite(img, colored_bg, vignette)

        # Save result in a new file
        output_path = os.path.join(path, 'processed')
        os.makedirs(output_path, exist_ok=True)
        result.save(os.path.join(output_path, image))
    except Exception as e:
        print(f"Error processing {image}: {e}")

#@lru_cache(maxsize=None)
def process_images(path, step):
    try:
        progress_bar = ctk.CTkProgressBar(master=frame, width=400, fg_color=("#FF0000", "#B22222"), progress_color=("#32CD32", "#006400"), mode="determinate")
        progress_bar.set(0)
        progress_bar.place(relx=0.5, rely=0.9, anchor='center')

        files = sorted(os.listdir(path))
        total_files = len(files)
        progress_step = step / total_files  # Calculate progress step as a percentage of total files
        progress = 0
        for i, file in enumerate(files):
            if i % step == 0:
                start = time.time()
                edit_image(path, file, RADIUS)
                print(time.time() - start)
                progress += progress_step
                progress_bar.set(progress)

        global label_complete
        if label_complete:
            label_complete.destroy()

        label_complete = ctk.CTkLabel(master=frame, text='All images completed!', bg_color="#e0e0e0")
        label_complete.place(relx=0.5, rely=0.955, anchor='center')
        label_complete.update()

        # Reset processing flag
        global processing
        processing = False

        # Re-enable the "Continue" button after processing is complete
        continue_button.configure(state='normal')

        window.deiconify()
        window.after_idle(window.attributes, '-topmost', False)

    except FileNotFoundError:
        error_label = ctk.CTkLabel(master=frame, text='Incorrect path name\n\nCheck your path name and try again.', bg_color="#e0e0e0")
        error_label.place(relx=0.5, rely=0.7, anchor='center')
        error_label.update()
        continue_button.configure(state='normal')  # Re-enable the "Continue" button in case of error
        processing = False  # Reset processing flag

def handle_keypress(event=None):
    global processing
    if processing:  # If processing is already ongoing, return
        return

    try:
        error_label.destroy()
    except NameError:
        pass

    global label_complete
    if label_complete:
        label_complete.destroy()

    # Disable the "Continue" button while processing
    continue_button.configure(state='disabled')

    # Set processing flag
    processing = True

    threading.Thread(target=process_images, args=(entry_path.get(), int(spinbox_value.get()))).start()

def update_radius(*args):
    global RADIUS
    try:
        RADIUS = int(vignette_strength_value.get())
    except ValueError:  # This is if the user removes everything from the spinbox
        pass

def choose_color():
    global chosen_color
    color = colorchooser.askcolor(title="Choose color for soft edge")[1]  # Get the hexadecimal color value
    if color:  # Check if a color was selected
        chosen_color = color
        soft_edge_color.configure(fg_color=chosen_color)  # Update the foreground color of the button

def choose_folder():
    folder_selected = filedialog.askdirectory()
    if folder_selected:
        entry_path.delete(0, tkinter.END)
        entry_path.insert(0, folder_selected)

# Create the main window
window = ctk.CTk()
window.geometry("500x500")
window.resizable(False, False)
window.title("Image Processor")
ico = Image.open("icon.ico")
photo = ImageTk.PhotoImage(ico)
window.wm_iconphoto(False, photo)

# Create the main frame
frame = ctk.CTkFrame(master=window, width=500, height=500, bg_color="#e0e0e0")
frame.pack(pady=20, padx=20, fill="both", expand=True)

# Create the path label
path_label = ctk.CTkLabel(master=frame, text='Please input path to images', text_color="#333333")
path_label.place(relx=0.5, rely=0.1, anchor='center')
path_label.configure(font=("Helvetica", 16))

# Create the entry for the path
entry_path = ctk.CTkEntry(master=frame, width=300, border_color="#333333")
entry_path.place(relx=0.5, rely=0.2, anchor='center')
entry_path.bind('<Return>', handle_keypress)

#create folder dialog picker
folder_picker_button = ctk.CTkButton(master=frame, text="Choose Folder", command=choose_folder, fg_color="#4682B4", hover_color="#4169E1")
folder_picker_button.place(relx=0.5, rely=0.28, anchor='center')

# Create the spinbox label
spinbox_label = ctk.CTkLabel(master=frame, text='Select step interval for processing images:', text_color="#333333")
spinbox_label.place(relx=0.5, rely=0.35, anchor='center')
spinbox_label.configure(font=("Helvetica", 14))

# Create the spinbox for selecting step interval
spinbox_frame = ctk.CTkFrame(master=frame, fg_color="#e0e0e0")
spinbox_frame.place(relx=0.5, rely=0.45, anchor='center')

spinbox_value = ctk.StringVar(value="1")

def increment_spinbox():
    current_value = int(spinbox_value.get())
    spinbox_value.set(str(current_value + 1))

def decrement_spinbox():
    current_value = int(spinbox_value.get())
    if current_value > 1:
        spinbox_value.set(str(current_value - 1))

spinbox = ctk.CTkEntry(master=spinbox_frame, width=50, textvariable=spinbox_value, border_color="#333333")
spinbox.grid(row=0, column=1, padx=5)

spinbox_decrement_button = ctk.CTkButton(master=spinbox_frame, text='-', width=30, command=decrement_spinbox, fg_color="#4682B4", hover_color="#4169E1")
spinbox_decrement_button.grid(row=0, column=0, padx=5)

spinbox_increment_button = ctk.CTkButton(master=spinbox_frame, text='+', width=30, command=increment_spinbox, fg_color="#4682B4", hover_color="#4169E1")
spinbox_increment_button.grid(row=0, column=2, padx=5)

# Create the soft edge border thickness label
vignette_strength_label = ctk.CTkLabel(master=frame, text='Vignette Strength:', text_color="#333333")
vignette_strength_label.place(relx=0.5, rely=0.53, anchor='center')
vignette_strength_label.configure(font=("Helvetica", 14))

# Create the spinbox for selecting the vignette_strength
vignette_strength_frame = ctk.CTkFrame(master=frame, fg_color="#e0e0e0")
vignette_strength_frame.place(relx=0.5, rely=0.6, anchor='center')

vignette_strength_value = ctk.StringVar(value="1.9")  # Default thickness value

def increment_vignette_strength():
    try:
        current_value = float(vignette_strength_value.get())
        vignette_strength_value.set(f"{current_value + 0.1:.1f}")
        update_radius()
    except ValueError:
        vignette_strength_value.set("1.9")

def decrement_vignette_strength():
    try:
        current_value = float(vignette_strength_value.get())
        if current_value > 0.0:
            vignette_strength_value.set(f"{current_value - 0.1:.1f}")
            update_radius()
    except ValueError:
        vignette_strength_value.set("1.9")

# Create the border thickness spinbox
vignette_strength_spinbox = ctk.CTkEntry(master=vignette_strength_frame, width=50, textvariable=vignette_strength_value, border_color="#333333")
vignette_strength_spinbox.grid(row=0, column=1, padx=5)

vignette_strength_value.trace_add('write', update_radius)

# Create the decrement button for decreasing border thickness
vignette_strength_decrement_button = ctk.CTkButton(master=vignette_strength_frame, text='-', width=30, command=decrement_vignette_strength, fg_color="#4682B4", hover_color="#4169E1")
vignette_strength_decrement_button.grid(row=0, column=0, padx=5)

# Create the increment button for increasing border thickness
vignette_strength_increment_button = ctk.CTkButton(master=vignette_strength_frame, text='+', width=30, command=increment_vignette_strength, fg_color="#4682B4", hover_color="#4169E1")
vignette_strength_increment_button.grid(row=0, column=2, padx=5)

# Soft Edge Color Label
soft_edge_color_label = ctk.CTkLabel(master=frame, text="Soft Edge Color", text_color="#333333")
soft_edge_color_label.place(relx=0.5, rely=0.7, anchor='center')
soft_edge_color_label.configure(font=("Helvetica", 14))

# Soft Edge Color Button
soft_edge_color = ctk.CTkButton(master=frame, text='', command=choose_color, fg_color=chosen_color, hover_color=chosen_color, width=30)
soft_edge_color.place(anchor='center', relx=0.5, rely=0.77)

# Create the continue button
continue_button = ctk.CTkButton(master=frame, text='Continue', command=handle_keypress, fg_color="#4682B4", hover_color="#4169E1", width=100)
continue_button.place(anchor='center', relx=0.5, rely=0.85)

RADIUS = float(vignette_strength_value.get())

# Run the main loop
window.mainloop()
'''

import customtkinter as ctk
import tkinter
from tkinter import colorchooser, filedialog
from PIL import Image, ImageDraw, ImageFilter, ImageTk
import numpy as np
import math
import os, time
import threading

chosen_color = "#000000"
label_complete = None
processing = False  # Track if processing is already ongoing

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def create_circular_mask(size, radius, vignette_strength):
    width, height = size
    Y, X = np.ogrid[:height, :width]
    center_x, center_y = width // 2, height // 2

    # Calculate the distance of each pixel from the center
    dist = np.sqrt((X - center_x)**2 + (Y - center_y)**2)

    # Normalize the distance
    max_dist = np.sqrt(center_x**2 + center_y**2)
    norm_dist = dist / max_dist

    # Create the mask using a radial gradient
    mask = 255 * (1 - norm_dist**vignette_strength)
    mask = np.clip(mask, 0, 255).astype('uint8')

    # Convert numpy array to PIL Image
    mask_image = Image.fromarray(mask, mode='L')

    # Apply a slight Gaussian blur for smoother edges
    mask_image = mask_image.filter(ImageFilter.GaussianBlur(radius=radius // 30))

    return mask_image

def edit_image(path, image, vignette_strength=1.9, diagonal_radius=3):
    try:
        global chosen_color
        path = path + "\\"
        img = Image.open(path + image).convert("RGB")
        chosen_color_rgb = hex_to_rgb(chosen_color)

        # Calculate size
        width, height = img.size
        diagonal = math.sqrt(width**2 + height**2)
        radius = int(diagonal / diagonal_radius)

        vignette_strength = max(0.1, min(2.0, vignette_strength))

        # Create circular mask
        vignette = create_circular_mask((width, height), radius, vignette_strength)

        # Create a background with the chosen color
        colored_bg = Image.new("RGB", img.size, chosen_color_rgb)

        # Blend the original image with the colored background using the vignette mask
        result = Image.composite(img, colored_bg, vignette)

        # Save result in a new file
        output_path = os.path.join(path, 'processed')
        os.makedirs(output_path, exist_ok=True)
        result.save(os.path.join(output_path, image))
    except Exception as e:
        print(f"Error processing {image}: {e}")

def process_images(path, step):
    try:
        progress_bar = ctk.CTkProgressBar(master=frame, width=400, height=20, fg_color=("#FF0000", "#B22222"), progress_color=("#32CD32", "#006400"), mode="determinate")
        progress_bar.set(0)
        progress_bar.place(relx=0.5, rely=0.8, anchor='center')

        files = sorted(os.listdir(path))
        total_files = len(files)
        progress_step = step / total_files  # Calculate progress step as a percentage of total files
        progress = 0
        for i, file in enumerate(files):
            if i % step == 0:
                start = time.time()
                edit_image(path, file, float(vignette_strength_value.get()), float(diagonal_radius_value.get()))
                print(time.time() - start)
                progress += progress_step
                progress_bar.set(progress)

        global label_complete
        if label_complete:
            label_complete.destroy()

        label_complete = ctk.CTkLabel(master=frame, text='All images completed!', bg_color="#e0e0e0")
        label_complete.place(relx=0.5, rely=0.855, anchor='center')
        label_complete.update()

        # Reset processing flag
        global processing
        processing = False

        # Re-enable the "Continue" button after processing is complete
        continue_button.configure(state='normal')

        window.deiconify()
        window.after_idle(window.attributes, '-topmost', False)

    except FileNotFoundError:
        error_label = ctk.CTkLabel(master=frame, text='Incorrect path name\n\nCheck your path name and try again.', bg_color="#e0e0e0")
        error_label.place(relx=0.5, rely=0.7, anchor='center')
        error_label.update()
        continue_button.configure(state='normal')  # Re-enable the "Continue" button in case of error
        processing = False  # Reset processing flag

def handle_keypress(event=None):
    global processing
    if processing:  # If processing is already ongoing, return
        return

    try:
        error_label.destroy()
    except NameError:
        pass

    global label_complete
    if label_complete:
        label_complete.destroy()

    # Disable the "Continue" button while processing
    continue_button.configure(state='disabled')

    # Set processing flag
    processing = True

    threading.Thread(target=process_images, args=(entry_path.get(), int(spinbox_value.get()))).start()

def update_radius(*args):
    global RADIUS
    try:
        RADIUS = int(vignette_strength_value.get())
    except ValueError:  # This is if the user removes everything from the spinbox
        pass

def choose_color():
    global chosen_color
    color = colorchooser.askcolor(title="Choose color for soft edge")[1]  # Get the hexadecimal color value
    if color:  # Check if a color was selected
        chosen_color = color
        soft_edge_color.configure(fg_color=chosen_color)  # Update the foreground color of the button

def choose_folder():
    folder_selected = filedialog.askdirectory()
    if folder_selected:
        entry_path.delete(0, tkinter.END)
        entry_path.insert(0, folder_selected)

# Create the main window
window = ctk.CTk()
window.geometry("500x650")
window.resizable(False, False)
window.title("Image Processor")
ico = Image.open("icon.ico")
photo = ImageTk.PhotoImage(ico)
window.wm_iconphoto(False, photo)

# Create the main frame
frame = ctk.CTkFrame(master=window, width=500, height=650, bg_color="#e0e0e0")
frame.pack(pady=20, padx=20, fill="both", expand=True)

# Create the path label
path_label = ctk.CTkLabel(master=frame, text='Please input path to images', text_color="#333333")
path_label.place(relx=0.5, rely=0.05, anchor='center')
path_label.configure(font=("Helvetica", 16))

# Create the entry for the path
entry_path = ctk.CTkEntry(master=frame, width=300, border_color="#333333")
entry_path.place(relx=0.5, rely=0.1, anchor='center')
entry_path.bind('<Return>', handle_keypress)

# Create folder dialog picker
folder_picker_button = ctk.CTkButton(master=frame, text="Choose Folder", command=choose_folder, fg_color="#4682B4", hover_color="#4169E1")
folder_picker_button.place(relx=0.5, rely=0.16, anchor='center')

# Create the spinbox label
spinbox_label = ctk.CTkLabel(master=frame, text='Select step interval for processing images:', text_color="#333333")
spinbox_label.place(relx=0.5, rely=0.22, anchor='center')
spinbox_label.configure(font=("Helvetica", 14))

# Create the spinbox for selecting step interval
spinbox_frame = ctk.CTkFrame(master=frame, fg_color="#e0e0e0")
spinbox_frame.place(relx=0.5, rely=0.27, anchor='center')

spinbox_value = ctk.StringVar(value="1")

def increment_spinbox():
    current_value = int(spinbox_value.get())
    spinbox_value.set(str(current_value + 1))

def decrement_spinbox():
    current_value = int(spinbox_value.get())
    if current_value > 1:
        spinbox_value.set(str(current_value - 1))

spinbox = ctk.CTkEntry(master=spinbox_frame, width=50, textvariable=spinbox_value, border_color="#333333")
spinbox.grid(row=0, column=1, padx=5)

spinbox_decrement_button = ctk.CTkButton(master=spinbox_frame, text='-', width=30, command=decrement_spinbox, fg_color="#4682B4", hover_color="#4169E1")
spinbox_decrement_button.grid(row=0, column=0, padx=5)

spinbox_increment_button = ctk.CTkButton(master=spinbox_frame, text='+', width=30, command=increment_spinbox, fg_color="#4682B4", hover_color="#4169E1")
spinbox_increment_button.grid(row=0, column=2, padx=5)

# Create the soft edge border thickness label
vignette_strength_label = ctk.CTkLabel(master=frame, text='Vignette Strength:', text_color="#333333")
vignette_strength_label.place(relx=0.5, rely=0.34, anchor='center')
vignette_strength_label.configure(font=("Helvetica", 14))

# Create the spinbox for selecting the vignette_strength
vignette_strength_frame = ctk.CTkFrame(master=frame, fg_color="#e0e0e0")
vignette_strength_frame.place(relx=0.5, rely=0.39, anchor='center')

vignette_strength_value = ctk.StringVar(value="1.9")  # Default thickness value

def increment_vignette_strength():
    try:
        current_value = float(vignette_strength_value.get())
        vignette_strength_value.set(f"{current_value + 0.1:.1f}")
        update_radius()
    except ValueError:
        vignette_strength_value.set("1.9")

def decrement_vignette_strength():
    try:
        current_value = float(vignette_strength_value.get())
        if current_value > 0.0:
            vignette_strength_value.set(f"{current_value - 0.1:.1f}")
            update_radius()
    except ValueError:
        vignette_strength_value.set("1.9")

# Create the border thickness spinbox
vignette_strength_spinbox = ctk.CTkEntry(master=vignette_strength_frame, width=50, textvariable=vignette_strength_value, border_color="#333333")
vignette_strength_spinbox.grid(row=0, column=1, padx=5)

vignette_strength_value.trace_add('write', update_radius)

# Create the decrement button for decreasing border thickness
vignette_strength_decrement_button = ctk.CTkButton(master=vignette_strength_frame, text='-', width=30, command=decrement_vignette_strength, fg_color="#4682B4", hover_color="#4169E1")
vignette_strength_decrement_button.grid(row=0, column=0, padx=5)

# Create the increment button for increasing border thickness
vignette_strength_increment_button = ctk.CTkButton(master=vignette_strength_frame, text='+', width=30, command=increment_vignette_strength, fg_color="#4682B4", hover_color="#4169E1")
vignette_strength_increment_button.grid(row=0, column=2, padx=5)

# Create the diagonal radius label
diagonal_radius_label = ctk.CTkLabel(master=frame, text='Vignette Radius:', text_color="#333333")
diagonal_radius_label.place(relx=0.5, rely=0.46, anchor='center')
diagonal_radius_label.configure(font=("Helvetica", 14))

# Create the spinbox for selecting the diagonal radius
diagonal_radius_frame = ctk.CTkFrame(master=frame, fg_color="#e0e0e0")
diagonal_radius_frame.place(relx=0.5, rely=0.51, anchor='center')

diagonal_radius_value = ctk.StringVar(value="3")  # Default diagonal radius value

def increment_diagonal_radius():
    try:
        current_value = float(diagonal_radius_value.get())
        diagonal_radius_value.set(f"{current_value + 1:.1f}")
    except ValueError:
        diagonal_radius_value.set("3")

def decrement_diagonal_radius():
    try:
        current_value = float(diagonal_radius_value.get())
        if current_value > 1:
            diagonal_radius_value.set(f"{current_value - 1:.1f}")
    except ValueError:
        diagonal_radius_value.set("3")

# Create the diagonal radius spinbox
diagonal_radius_spinbox = ctk.CTkEntry(master=diagonal_radius_frame, width=50, textvariable=diagonal_radius_value, border_color="#333333")
diagonal_radius_spinbox.grid(row=0, column=1, padx=5)

# Create the decrement button for decreasing diagonal radius
diagonal_radius_decrement_button = ctk.CTkButton(master=diagonal_radius_frame, text='-', width=30, command=decrement_diagonal_radius, fg_color="#4682B4", hover_color="#4169E1")
diagonal_radius_decrement_button.grid(row=0, column=0, padx=5)

# Create the increment button for increasing diagonal radius
diagonal_radius_increment_button = ctk.CTkButton(master=diagonal_radius_frame, text='+', width=30, command=increment_diagonal_radius, fg_color="#4682B4", hover_color="#4169E1")
diagonal_radius_increment_button.grid(row=0, column=2, padx=5)

# Soft Edge Color Label
soft_edge_color_label = ctk.CTkLabel(master=frame, text="Soft Edge Color", text_color="#333333")
soft_edge_color_label.place(relx=0.5, rely=0.58, anchor='center')
soft_edge_color_label.configure(font=("Helvetica", 14))

# Soft Edge Color Button
soft_edge_color = ctk.CTkButton(master=frame, text='', command=choose_color, fg_color=chosen_color, hover_color=chosen_color, width=30)
soft_edge_color.place(anchor='center', relx=0.5, rely=0.63)

# Create the continue button
continue_button = ctk.CTkButton(master=frame, text='Continue', command=handle_keypress, fg_color="#4682B4", hover_color="#4169E1", width=100)
continue_button.place(anchor='center', relx=0.5, rely=0.7)

RADIUS = float(vignette_strength_value.get())

# Run the main loop
window.mainloop()
