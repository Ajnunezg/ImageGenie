import os
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import replicate
from PIL import Image, ImageTk, ImageDraw, ImageFilter
import io
import requests
import re
import time
import json
import concurrent.futures
from datetime import datetime
import math
import sqlite3
import uuid
import pandas as pd
from collections import Counter

# Import ImageCarousel from carousel module
from carousel import ImageCarousel, RoundedButton

# Custom UI elements and themes
from tkinter import font


class ImageGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Image Generator")
        self.root.geometry("900x700")
        self.root.configure(bg="#f0f0f0")

        # Set application style
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Configure colors for better contrast
        self.primary_color = "#FF9933"  # Tangerine orange
        self.bg_color = "#f0f0f0"  # Light gray background
        self.text_color = "#333333"  # Dark gray text for high contrast
        self.button_text_color = "#000000"  # Black text on buttons for maximum contrast
        self.accent_color = "#FF8C00"  # Darker tangerine for accents

        # Configure styles with improved contrast
        self.style.configure('TFrame', background=self.bg_color)
        self.style.configure('TLabel', background=self.bg_color, font=('Helvetica', 12), foreground=self.text_color)
        self.style.configure('TEntry', font=('Helvetica', 12))
        self.style.configure('TButton',
                             font=('Helvetica', 12, 'bold'),
                             background=self.primary_color,
                             foreground=self.button_text_color)

        # Additional style for image frame
        self.style.configure('ImageBg.TFrame', background='#ffffff', relief='groove', borderwidth=2)

        # Available models dictionary with name and ID
        self.available_models = {
            "Flux Schnell": "black-forest-labs/flux-schnell",
            "Recraft-v3": "recraft-ai/recraft-v3",
            "Imagen 3": "google/imagen-3",
            "Ideogram-v2a-turbo": "ideogram-ai/ideogram-v2a-turbo",
            "Byte Dance SDXL": "bytedance/sdxl-lightning-4step:6f7a773af6fc3e8de9d5a3c00be77c17308914bf67772726aff83496ba1e3bbe",
            "Imagen 3 Fast": "google/imagen-3-fast",
            "Luma Photon Flash": "luma/photon-flash"

        }

        # Track generated images
        self.generated_images = []
        self.image_widgets = []

        # For tracking thread status
        self.active_generations = {}
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        self.generation_timeout = 180  # 3 minutes timeout

        # Settings directory and file
        self.settings_dir = os.path.join(os.path.expanduser('~'), '.imagegenie')
        self.settings_file = os.path.join(self.settings_dir, 'settings.json')

        # Create output directory
        self.output_dir = "generated_images"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        # Create settings directory if it doesn't exist
        if not os.path.exists(self.settings_dir):
            os.makedirs(self.settings_dir)

        # Database setup
        self.db_path = os.path.join(self.settings_dir, 'rankings.db')
        self.init_database()

        # Current user
        self.current_user_id = None
        self.username = "Anonymous User"

        # Image carousel reference
        self.carousel = None
        self.carousel_images = []

        # Flag to track if token has been set and should be hidden
        self.token_is_set = False

        # Arena mode flag
        self.arena_mode = False

        # Create menu bar
        self.create_menu()

        self.create_widgets()
        self.load_saved_token()

    def create_menu(self):
        """Create application menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)

        # API Token menu item
        file_menu.add_command(label="Change API Token", command=self.show_api_token_dialog)

        # Cancel Generation menu item (initially disabled)
        self.cancel_menu_item = file_menu.add_command(
            label="Cancel Generation",
            command=self.cancel_generation,
            state=tk.DISABLED
        )

        # Show Status Log menu item
        file_menu.add_command(label="Show Status Log", command=self.show_status_log)
        
        # Gallery menu item
        file_menu.add_command(label="Image Gallery", command=self.show_gallery)

        # Arena Mode menu item
        self.arena_mode_menu_item = file_menu.add_command(
            label="Enter Arena Mode",
            command=self.toggle_arena_mode
        )

        # Leaderboard menu item
        file_menu.add_command(label="Show Leaderboard", command=self.show_leaderboard)

        # User menu item
        file_menu.add_command(label="Set Username", command=self.set_username)

        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
        
    def toggle_arena_mode(self):
        """Toggle between entering and exiting Arena Mode"""
        if self.arena_mode:
            self.exit_arena_mode()
            
            # Update menu label
            menubar = self.root.nametowidget(self.root.cget("menu"))
            file_menu = menubar.nametowidget(menubar.entrycget(0, "menu"))
            file_menu.entryconfigure("Exit Arena Mode", label="Enter Arena Mode")
        else:
            self.enter_arena_mode()
            
            # Update menu label
            menubar = self.root.nametowidget(self.root.cget("menu"))
            file_menu = menubar.nametowidget(menubar.entrycget(0, "menu"))
            file_menu.entryconfigure("Enter Arena Mode", label="Exit Arena Mode")

    def enter_arena_mode(self):
        """Enter Arena Mode: select all models, generate one image each, and enable voting"""
        if not self.prompt_text.get("1.0", tk.END).strip():
            messagebox.showerror("Error", "Please enter an image prompt")
            return
        self.arena_mode = True
        self.model_selector.select_all()
        self.images_per_model.set(1)
        
        # Update window title
        self.root.title("AI Image Generator - Arena Mode")
        
        # Apply arcade retro theme
        self.apply_arena_mode_theme()
        
        # Message to inform user
        messagebox.showinfo("Arena Mode Activated", "Arena Mode is now active. All models have been selected.\n\nClick 'Generate Images' to start the battle!")

    def apply_arena_mode_theme(self):
        """Apply the arcade retro theme for Arena Mode"""
        # Store original colors for later restoration
        self.original_colors = {
            "bg_color": self.bg_color,
            "primary_color": self.primary_color,
            "text_color": self.text_color,
            "button_text_color": self.button_text_color,
            "accent_color": self.accent_color
        }
        
        # Set arcade theme colors
        self.bg_color = "#000000"  # Black background
        self.primary_color = "#00FF00"  # Neon green
        self.text_color = "#00FF00"  # Neon green text
        self.button_text_color = "#000000"  # Black text on buttons
        self.accent_color = "#FF00FF"  # Magenta accent
        
        # Apply colors to existing UI elements
        self.root.configure(bg=self.bg_color)
        
        # Update styles
        self.style.configure('TFrame', background=self.bg_color)
        self.style.configure('TLabel', background=self.bg_color, foreground=self.text_color)
        self.style.configure('TButton', 
                          background=self.primary_color,
                          foreground=self.button_text_color)
        
        # Update text widgets
        self.prompt_text.config(background="#111111", foreground=self.primary_color)
        
        # Create pixelated border for widgets
        self.create_pixelated_borders()
        
        # Update buttons
        self.generate_button.config(bg=self.primary_color, fg=self.button_text_color)
        
        # Update embedded carousel
        if hasattr(self, 'embedded_image_frame'):
            self.embedded_image_frame.configure(style='ArcadeFrame.TFrame')
            
        # Add arcade style to the style configuration
        self.style.configure('ArcadeFrame.TFrame', background="#111111", 
                          relief='ridge', borderwidth=3)
        
        # Update navigation buttons
        if hasattr(self, 'embedded_left_btn'):
            self.embedded_left_btn.config(bg=self.primary_color, fg=self.button_text_color)
        if hasattr(self, 'embedded_right_btn'):
            self.embedded_right_btn.config(bg=self.primary_color, fg=self.button_text_color)
            
        # Add pixelated font if available
        try:
            pixel_font = font.Font(family="Press Start 2P", size=10)
            self.generate_button.config(font=pixel_font)
        except:
            # Fall back to a basic font if pixel font not available
            self.generate_button.config(font=('Courier', 11, 'bold'))

    def create_pixelated_borders(self):
        """Create pixelated borders for widgets to enhance arcade look"""
        # This is a visual enhancement that adds pixelated borders to frames
        for widget in self.root.winfo_children():
            if isinstance(widget, ttk.Frame):
                self.style.configure(f'Pixelated.TFrame', 
                                  background=self.bg_color,
                                  borderwidth=2, 
                                  relief="raised")
                widget.configure(style='Pixelated.TFrame')

    def exit_arena_mode(self):
        """Exit Arena Mode and restore original UI"""
        self.arena_mode = False
        self.root.title("AI Image Generator")
        
        # Restore original colors
        if hasattr(self, 'original_colors'):
            self.bg_color = self.original_colors["bg_color"]
            self.primary_color = self.original_colors["primary_color"]
            self.text_color = self.original_colors["text_color"]
            self.button_text_color = self.original_colors["button_text_color"]
            self.accent_color = self.original_colors["accent_color"]
            
            # Reapply original theme
            self.root.configure(bg=self.bg_color)
            
            # Update styles
            self.style.configure('TFrame', background=self.bg_color)
            self.style.configure('TLabel', background=self.bg_color, foreground=self.text_color)
            self.style.configure('TButton', 
                              background=self.primary_color,
                              foreground=self.button_text_color)
            
            # Update text widgets
            self.prompt_text.config(background="#FAFAFA", foreground="#333333")
            
            # Update buttons
            self.generate_button.config(bg=self.primary_color, fg=self.button_text_color)
            
            # Update embedded carousel
            if hasattr(self, 'embedded_image_frame'):
                self.embedded_image_frame.configure(style='ImageBg.TFrame')
                
            # Update navigation buttons
            if hasattr(self, 'embedded_left_btn'):
                self.embedded_left_btn.config(bg=self.primary_color, fg=self.button_text_color)
            if hasattr(self, 'embedded_right_btn'):
                self.embedded_right_btn.config(bg=self.primary_color, fg=self.button_text_color)
            
            # Reset font
            self.generate_button.config(font=('Helvetica', 11, 'bold'))

    def show_api_token_dialog(self):
        """Show a dialog to change the API token"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Change API Token")
        dialog.geometry("400x200")
        dialog.resizable(False, False)
        dialog.transient(self.root)  # Make dialog modal
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (dialog.winfo_screenheight() // 2) - (height // 2)
        dialog.geometry(f'{width}x{height}+{x}+{y}')

        # Content frame
        content_frame = ttk.Frame(dialog, padding=20)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Token label and entry
        ttk.Label(content_frame, text="Enter Replicate API Token:").pack(anchor=tk.W, pady=(0, 5))

        token_entry = ttk.Entry(content_frame, width=40, show="•")
        token_entry.pack(fill=tk.X, pady=(0, 10))

        # Pre-fill with existing token if available
        current_token = self.token_entry.get() if hasattr(self, 'token_entry') else ""
        if current_token:
            token_entry.insert(0, current_token)

        # Save checkbox
        save_token_var = tk.BooleanVar(value=self.save_token_var.get() if hasattr(self, 'save_token_var') else False)
        ttk.Checkbutton(content_frame, text="Save API Token", variable=save_token_var).pack(anchor=tk.W)

        # Button frame
        button_frame = ttk.Frame(content_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        # Save button
        save_button = ttk.Button(
            button_frame,
            text="Save",
            command=lambda: self.save_api_token_from_dialog(token_entry.get(), save_token_var.get(), dialog)
        )
        save_button.pack(side=tk.RIGHT, padx=5)

        # Cancel button
        cancel_button = ttk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy
        )
        cancel_button.pack(side=tk.RIGHT, padx=5)

    def save_api_token_from_dialog(self, token, save, dialog):
        """Save the API token entered in the dialog"""
        if not token:
            messagebox.showerror("Error", "Please enter an API token", parent=dialog)
            return

        # Update token entry if it exists
        if hasattr(self, 'token_entry'):
            self.token_entry.delete(0, tk.END)
            self.token_entry.insert(0, token)

        # Update save checkbox
        if hasattr(self, 'save_token_var'):
            self.save_token_var.set(save)

        # Save to file if requested
        if save:
            self.save_token_to_file(token)

        # Set environment variable
        os.environ["REPLICATE_API_TOKEN"] = token

        # Mark token as set to hide the entry field
        self.token_is_set = True

        # Hide token frame if it exists
        if hasattr(self, 'token_frame'):
            self.token_frame.pack_forget()

        # Add log message
        self.add_log("API token updated successfully")
        dialog.destroy()

    def show_about(self):
        """Show the about dialog"""
        about_dialog = tk.Toplevel(self.root)
        about_dialog.title("About ImageGenie")
        about_dialog.geometry("400x300")
        about_dialog.resizable(False, False)
        about_dialog.transient(self.root)

        # Center dialog
        about_dialog.update_idletasks()
        width = about_dialog.winfo_width()
        height = about_dialog.winfo_height()
        x = (about_dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (about_dialog.winfo_screenheight() // 2) - (height // 2)
        about_dialog.geometry(f'{width}x{height}+{x}+{y}')

        content_frame = ttk.Frame(about_dialog, padding=20)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # App title
        ttk.Label(content_frame, text="ImageGenie", font=("Helvetica", 16, "bold")).pack(pady=(0, 10))

        # Description
        description = "A desktop application for generating images with AI models from Replicate"
        ttk.Label(content_frame, text=description, wraplength=350).pack(pady=(0, 20))

        # Version
        ttk.Label(content_frame, text="Version 1.0").pack()

        # Close button
        ttk.Button(content_frame, text="Close", command=about_dialog.destroy).pack(pady=(20, 0))

    def create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title
        title_label = ttk.Label(main_frame, text=" ImageGenie ", font=('Helvetica', 16, 'bold'))
        title_label.pack(pady=(0, 20))

        # Left panel for controls
        left_panel = ttk.Frame(main_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Right panel for image display
        self.right_panel = ttk.Frame(main_frame)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Add embedded carousel to right panel
        self.embedded_carousel_frame = ttk.Frame(self.right_panel)
        self.embedded_carousel_frame.pack(fill=tk.BOTH, expand=True)

        # Carousel heading
        carousel_header = ttk.Frame(self.embedded_carousel_frame)
        carousel_header.pack(fill=tk.X)

        carousel_title = ttk.Label(carousel_header, text="", font=('Helvetica', 14, 'bold'))
        carousel_title.pack(side=tk.LEFT, pady=5)

        # Create the embedded carousel components
        self.create_embedded_carousel()

        # API Token frame - will be hidden once token is set
        self.token_frame = ttk.Frame(left_panel)
        self.token_frame.pack(fill=tk.X, pady=10)

        token_label = ttk.Label(self.token_frame, text="Replicate API Token:")
        token_label.pack(anchor=tk.W)

        self.token_entry = ttk.Entry(self.token_frame, width=30, show="•")
        self.token_entry.pack(fill=tk.X, pady=5)

        # Save token checkbox
        self.save_token_var = tk.BooleanVar(value=False)
        save_token_cb = ttk.Checkbutton(
            self.token_frame,
            text="Save API Token",
            variable=self.save_token_var
        )
        save_token_cb.pack(anchor=tk.W, pady=(0, 5))

        # Preset token from environment if available
        api_token = os.environ.get("REPLICATE_API_TOKEN", "")
        if api_token:
            self.token_entry.insert(0, api_token)

        # Prompt frame
        prompt_frame = ttk.Frame(left_panel)
        prompt_frame.pack(fill=tk.X, pady=10)

        # Prompt label with enhance button
        prompt_header = ttk.Frame(prompt_frame)
        prompt_header.pack(fill=tk.X)

        prompt_label = ttk.Label(prompt_header, text="Image Prompt:")
        prompt_label.pack(side=tk.LEFT, anchor=tk.W)

        enhance_button = tk.Button(
            prompt_header,
            text="✨ Enhance",
            bg=self.primary_color,
            fg=self.button_text_color,
            font=('Helvetica', 9, 'bold'),
            relief=tk.RAISED,
            borderwidth=1,
            padx=5,
            pady=2,
            command=self.enhance_prompt
        )
        enhance_button.pack(side=tk.RIGHT, padx=(5, 0))

        self.prompt_text = scrolledtext.ScrolledText(
            prompt_frame,
            height=4,
            width=30,
            wrap=tk.WORD,
            font=('Helvetica', 10),
            background="#FAFAFA",
            foreground="#333333",
            insertbackground="#333333"
        )
        self.prompt_text.pack(fill=tk.X, pady=5)
        self.prompt_text.insert(tk.END, "Starry Night in NYC, in the style of Vincent Van Gogh's Starry Night")

        # Enhanced prompt frame (initially hidden)
        self.enhanced_prompt_frame = ttk.Frame(prompt_frame)

        enhanced_label = ttk.Label(self.enhanced_prompt_frame, text="Enhanced Prompt Suggestion:")
        enhanced_label.pack(anchor=tk.W, pady=(10, 5))

        self.enhanced_prompt_text = scrolledtext.ScrolledText(
            self.enhanced_prompt_frame,
            height=6,
            width=30,
            wrap=tk.WORD,
            font=('Helvetica', 10),
            background="#F5FAFF",
            foreground=self.primary_color
        )
        self.enhanced_prompt_text.pack(fill=tk.X, pady=5)

        # Button frame in enhanced prompt
        btn_frame = ttk.Frame(self.enhanced_prompt_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 5))

        use_suggestion_btn = tk.Button(
            btn_frame,
            text="Use This",
            bg=self.primary_color,
            fg=self.button_text_color,
            font=('Helvetica', 9, 'bold'),
            relief=tk.RAISED,
            borderwidth=2,
            padx=5,
            pady=2,
            command=self.use_enhanced_prompt
        )
        use_suggestion_btn.pack(side=tk.LEFT)

        dismiss_btn = tk.Button(
            btn_frame,
            text="Dismiss",
            bg="#CCCCCC",
            fg=self.button_text_color,
            font=('Helvetica', 9),
            relief=tk.RAISED,
            borderwidth=2,
            padx=5,
            pady=2,
            command=lambda: self.enhanced_prompt_frame.pack_forget()
        )
        dismiss_btn.pack(side=tk.LEFT, padx=(5, 0))

        # Model selection frame with dropdown
        model_frame = ttk.Frame(left_panel)
        model_frame.pack(fill=tk.X, pady=10)

        model_label = ttk.Label(model_frame, text="Select Models:")
        model_label.pack(anchor=tk.W)

        dropdown_frame = ttk.Frame(model_frame)
        dropdown_frame.pack(fill=tk.X, pady=5)

        self.model_selector = MultiSelectDropdown(
            dropdown_frame,
            options=list(self.available_models.keys()),
            width=30,
            placeholder="Select models...",
            bg_color=self.bg_color,
            select_color=self.primary_color
        )
        self.model_selector.pack(fill=tk.X)

        first_model = list(self.available_models.keys())[0]
        self.model_selector.select_item(first_model)

        # Advanced options frame (collapsible)
        self.advanced_frame = ttk.Frame(left_panel)
        self.advanced_frame.pack(fill=tk.X, pady=5)

        self.show_advanced = tk.BooleanVar(value=False)
        self.advanced_toggle = ttk.Checkbutton(
            self.advanced_frame,
            text="Show Advanced Options",
            variable=self.show_advanced,
            command=self.toggle_advanced_options
        )
        self.advanced_toggle.pack(anchor=tk.W)

        self.advanced_options = ttk.Frame(left_panel)

        custom_model_frame = ttk.Frame(self.advanced_options)
        custom_model_frame.pack(fill=tk.X, pady=5)

        custom_model_label = ttk.Label(custom_model_frame, text="Custom Model ID:")
        custom_model_label.pack(anchor=tk.W)

        self.custom_model_entry = ttk.Entry(custom_model_frame, width=30)
        self.custom_model_entry.pack(fill=tk.X, pady=5)

        self.use_custom_model = tk.BooleanVar(value=False)
        custom_model_cb = ttk.Checkbutton(
            custom_model_frame,
            text="Use Custom Model",
            variable=self.use_custom_model
        )
        custom_model_cb.pack(anchor=tk.W)

        multi_image_frame = ttk.Frame(self.advanced_options)
        multi_image_frame.pack(fill=tk.X, pady=5)

        multi_image_label = ttk.Label(multi_image_frame, text="Images per model:")
        multi_image_label.pack(anchor=tk.W)

        counter_frame = ttk.Frame(multi_image_frame)
        counter_frame.pack(anchor=tk.W, pady=5)

        self.images_per_model = tk.IntVar(value=1)

        decrement_btn = ttk.Button(
            counter_frame,
            text="-",
            width=2,
            command=lambda: self.update_images_count(-1)
        )
        decrement_btn.pack(side=tk.LEFT)

        count_label = ttk.Label(
            counter_frame,
            textvariable=self.images_per_model,
            width=3,
            anchor=tk.CENTER
        )
        count_label.pack(side=tk.LEFT, padx=5)

        increment_btn = ttk.Button(
            counter_frame,
            text="+",
            width=2,
            command=lambda: self.update_images_count(1)
        )
        increment_btn.pack(side=tk.LEFT)

        help_text = ttk.Label(
            multi_image_frame,
            text="Generate multiple images from each selected model.",
            font=("Helvetica", 9),
            foreground="#666666"
        )
        help_text.pack(anchor=tk.W, pady=(0, 5))

        timeout_frame = ttk.Frame(self.advanced_options)
        timeout_frame.pack(fill=tk.X, pady=5)

        timeout_label = ttk.Label(timeout_frame, text="Generation Timeout (seconds):")
        timeout_label.pack(anchor=tk.W)

        self.timeout_var = tk.StringVar(value=str(self.generation_timeout))
        timeout_entry = ttk.Entry(timeout_frame, width=10, textvariable=self.timeout_var)
        timeout_entry.pack(anchor=tk.W, pady=5)

        # Generate button
        button_frame = ttk.Frame(left_panel)
        button_frame.pack(fill=tk.X, pady=10)

        self.generate_button = tk.Button(
            button_frame,
            text="Generate Images",
            bg=self.primary_color,
            fg=self.button_text_color,
            font=('Helvetica', 11, 'bold'),
            relief=tk.RAISED,
            borderwidth=2,
            padx=15,
            pady=8,
            command=self.generate_images
        )
        self.generate_button.pack(pady=10)

        self.progress_var = tk.StringVar(value="")
        self.progress_label = ttk.Label(button_frame, textvariable=self.progress_var)
        self.progress_label.pack(pady=5)

        self.status_text = scrolledtext.ScrolledText(self.root, height=1, width=1)
        self.status_text.pack_forget()
        self.status_text.config(state=tk.DISABLED)

    def toggle_advanced_options(self):
        if self.show_advanced.get():
            self.advanced_options.pack(fill=tk.X, pady=5, after=self.advanced_frame)
        else:
            self.advanced_options.pack_forget()

    def get_selected_models(self):
        selected_models = []

        if self.show_advanced.get() and self.use_custom_model.get():
            custom_model = self.custom_model_entry.get().strip()
            if custom_model:
                return [("Custom Model", custom_model)]

        for model_name in self.model_selector.get_selected():
            model_id = self.available_models[model_name]
            selected_models.append((model_name, model_id))

        return selected_models

    def add_log(self, message):
        """Add a message to the log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"

        if hasattr(self, 'status_text'):
            self.status_text.config(state=tk.NORMAL)
            self.status_text.insert(tk.END, log_message)
            self.status_text.see(tk.END)
            self.status_text.config(state=tk.DISABLED)

        if hasattr(self, 'log_window') and self.log_window.winfo_exists():
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, log_message)
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)

    def save_token_to_file(self, token):
        """Save the API token to a settings file"""
        try:
            settings = {}
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)

            settings['api_token'] = token

            with open(self.settings_file, 'w') as f:
                json.dump(settings, f)

            self.token_is_set = True
            self.token_frame.pack_forget()

            self.add_log("API token saved successfully")
        except Exception as e:
            self.add_log(f"Error saving API token: {str(e)}")

    def load_saved_token(self):
        """Load the saved API token if available"""
        try:
            has_token = False

            api_token = os.environ.get("REPLICATE_API_TOKEN", "")
            if api_token:
                self.token_entry.delete(0, tk.END)
                self.token_entry.insert(0, api_token)
                self.save_token_var.set(True)
                has_token = True
                self.add_log("Using API token from environment")

            elif os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)

                if 'api_token' in settings and settings['api_token']:
                    self.token_entry.delete(0, tk.END)
                    self.token_entry.insert(0, settings['api_token'])
                    self.save_token_var.set(True)
                    has_token = True
                    self.add_log("Loaded saved API token")

            if has_token and self.save_token_var.get():
                self.token_is_set = True
                self.token_frame.pack_forget()

        except Exception as e:
            self.add_log(f"Error loading saved API token: {str(e)}")

    def generate_images(self):
        api_token = self.token_entry.get().strip()
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        selected_models = self.get_selected_models()

        if self.save_token_var.get() and api_token:
            self.save_token_to_file(api_token)

        if not api_token:
            messagebox.showerror("Error", "Please enter your Replicate API token")
            return

        if not prompt:
            messagebox.showerror("Error", "Please enter an image prompt")
            return

        if not selected_models:
            messagebox.showerror("Error", "Please select at least one model")
            return

        try:
            self.generation_timeout = int(self.timeout_var.get())
            if self.generation_timeout < 10:
                self.generation_timeout = 10
                self.timeout_var.set("10")
        except ValueError:
            self.generation_timeout = 180
            self.timeout_var.set("180")

        self.generate_button.config(state=tk.DISABLED)

        menubar = self.root.nametowidget(self.root.cget("menu"))
        file_menu = menubar.nametowidget(menubar.entrycget(0, "menu"))
        file_menu.entryconfigure("Cancel Generation", state=tk.NORMAL)

        self.progress_var.set(f"Generating images with {len(selected_models)} model(s)...")
        self.add_log(f"Starting generation with prompt: {prompt[:50]}{'...' if len(prompt) > 50 else ''}")

        self.carousel_images = []
        self.embedded_current_index = 0
        self.embedded_model_label.config(text="Generating images...")
        self.embedded_counter_label.config(text="")

        if self.carousel and self.carousel.winfo_exists():
            self.carousel.images = []
            self.carousel.current_index = 0
            self.carousel.update_display()

        self.active_generations = {}

        os.environ["REPLICATE_API_TOKEN"] = api_token

        images_per_model = self.images_per_model.get()

        generation_complete = threading.Event()

        futures = []
        for idx, (model_name, model_id) in enumerate(selected_models):
            for image_idx in range(images_per_model):
                if self.arena_mode:
                    display_name = f"Image {idx + 1}"
                    generation_name = model_name  # For logging
                else:
                    generation_name = model_name
                    if images_per_model > 1:
                        generation_name = f"{model_name} (Image {image_idx + 1})"
                    display_name = generation_name

                self.add_log(f"Queuing model: {generation_name}")
                self.active_generations[generation_name] = "queued"

                future = self.executor.submit(
                    self._generate_image_thread,
                    api_token,
                    prompt,
                    generation_name,
                    model_id,
                    idx * images_per_model + image_idx,
                    generation_complete,
                    display_name
                )
                futures.append(future)

        self.root.after(1000, self._check_generation_status, futures, generation_complete)

        # Initialize thread results dictionary for the timeout handling
        self.thread_results = {}

    def _generate_image_thread(self, api_token, prompt, generation_name, model_id, position, complete_event, display_name):
        try:
            self.root.after(0, lambda: self.add_log(f"Starting generation with {generation_name}..."))
            self.active_generations[generation_name] = "running"

            base_model_name = generation_name
            if "(" in generation_name and ")" in generation_name:
                base_model_name = generation_name.split("(")[0].strip()

            # Set a timeout for the Replicate API call
            timeout_seconds = 25  # Reduced timeout to 25 seconds as requested
            
            # Create and run a thread with a timeout
            output = None
            generation_thread = threading.Thread(
                target=lambda: self._run_model_with_timeout(model_id, prompt, generation_name)
            )
            generation_thread.daemon = True
            generation_thread.start()
            generation_thread.join(timeout=timeout_seconds)
            
            # Check if thread is still alive (meaning it timed out)
            if generation_thread.is_alive() or self.active_generations.get(generation_name) == "canceled":
                if generation_thread.is_alive():
                    self.root.after(0, lambda: self.add_log(f"Generation with {generation_name} timed out after {timeout_seconds} seconds"))
                    self.active_generations[generation_name] = "timeout"
                else:
                    self.root.after(0, lambda: self.add_log(f"Generation with {generation_name} was canceled"))
                return
                
            # Get the output from the thread's result
            output = self.thread_results.get(generation_name)
            if not output:
                raise ValueError("Model returned empty result")

            image_url = output[0] if isinstance(output, list) else output

            self.root.after(0, lambda: self.add_log(f"Downloading image from {generation_name}..."))

            # Set a timeout for the download request
            response = requests.get(image_url, timeout=10)
            if response.status_code == 200:
                image_data = response.content

                model_dir = os.path.join(self.output_dir, base_model_name.replace(" ", "_"))
                if not os.path.exists(model_dir):
                    os.makedirs(model_dir)

                sanitized_prompt = re.sub(r'[^\w\s-]', '', prompt)
                sanitized_prompt = re.sub(r'[\s-]+', '_', sanitized_prompt)
                sanitized_prompt = sanitized_prompt[:50]

                timestamp = int(time.time())
                filename = f"{sanitized_prompt}_{timestamp}.png"
                filepath = os.path.join(model_dir, filename)

                with open(filepath, 'wb') as f:
                    f.write(image_data)

                image = Image.open(io.BytesIO(image_data))

                # Save image to database
                self.root.after(0, lambda: self.save_image_to_database(filepath, prompt, generation_name, model_id))

                self.root.after(0, lambda: self.add_to_carousel(image, display_name, filepath, generation_name))

                self.root.after(0,
                                lambda: self.add_log(f"Image generated by {generation_name} and saved at {filepath}"))
            else:
                error_msg = f"Error downloading image from {generation_name}: HTTP {response.status_code}"
                self.root.after(0, lambda: self.add_log(error_msg))

        except requests.exceptions.Timeout:
            error_msg = f"Timeout downloading image from {generation_name}"
            self.root.after(0, lambda: self.add_log(error_msg))
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error with {generation_name}: {str(e)}"
            self.root.after(0, lambda: self.add_log(error_msg))
        except concurrent.futures.TimeoutError:
            error_msg = f"Generation timeout for {generation_name} after {timeout_seconds} seconds"
            self.root.after(0, lambda: self.add_log(error_msg))
        except Exception as e:
            error_msg = f"Failed to generate image with {generation_name}: {str(e)}"
            self.root.after(0, lambda: self.add_log(error_msg))
        finally:
            # Ensure the generation is marked as completed, even if it failed
            if self.active_generations.get(generation_name) == "running":
                self.active_generations[generation_name] = "completed"

            # Check if all generations are done (completed, canceled, or timed out)
            if all(status in ["completed", "canceled", "timeout"] for status in self.active_generations.values()):
                complete_event.set()
                
    def save_image_to_database(self, filepath, prompt, model_name, model_id):
        """Save the generated image information to the database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            image_id = str(uuid.uuid4())
            user_id = self.current_user_id if self.current_user_id else 'anonymous'
            
            cursor.execute('''
                INSERT INTO images (image_id, user_id, filepath, prompt, model_name, model_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (image_id, user_id, filepath, prompt, model_name, model_id))
            
            conn.commit()
            self.add_log(f"Image saved to database with ID: {image_id}")
            
        except sqlite3.Error as e:
            self.add_log(f"Database error while saving image: {str(e)}")
        finally:
            if conn:
                conn.close()

    def _check_generation_status(self, futures, complete_event):
        """Check the status of image generation threads and update UI"""
        # Count different states
        active_count = sum(1 for status in self.active_generations.values() if status in ["queued", "running"])
        completed_count = sum(1 for status in self.active_generations.values() if status == "completed")
        canceled_count = sum(1 for status in self.active_generations.values() if status == "canceled")
        timeout_count = sum(1 for status in self.active_generations.values() if status == "timeout")
        total_count = len(self.active_generations)

        if active_count > 0:
            self.progress_var.set(
                f"Generating: {completed_count}/{total_count} completed, {canceled_count} canceled, {timeout_count} timed out, {active_count} active")
            self.root.after(1000, self._check_generation_status, futures, complete_event)
        elif complete_event.is_set() or all(f.done() for f in futures):
            self.progress_var.set(
                f"Generation complete: {completed_count}/{total_count} images generated, {canceled_count} canceled, {timeout_count} timed out")
            self.re_enable_generate_button()

            # Check if we have any successful generations to show
            if self.carousel_images:
                if self.arena_mode and len(self.carousel_images) >= 2:  # Need at least 2 images to rank
                    self.show_voting_interface()
                else:
                    self.update_embedded_carousel()
                    # If in arena mode but not enough images, show message
                    if self.arena_mode and len(self.carousel_images) < 2:
                        messagebox.showinfo("Arena Mode", "Not enough images were generated successfully to enter Arena Mode ranking. Please try again with different models.")
        else:
            self.progress_var.set("All generations completed or timed out")
            self.re_enable_generate_button()

            if self.carousel_images:
                self.update_embedded_carousel()

    def show_voting_interface(self):
        """Show the voting interface for ranking images"""
        voting_window = tk.Toplevel(self.root)
        voting_window.title("ARENA MODE - Rank the Champions")
        voting_window.geometry("500x600")

        # Apply arcade theme if in arena mode
        if self.arena_mode:
            voting_window.configure(bg="#000000")
            
        voting_window.update_idletasks()
        width = voting_window.winfo_width()
        height = voting_window.winfo_height()
        x = (voting_window.winfo_screenwidth() // 2) - (width // 2)
        y = (voting_window.winfo_screenheight() // 2) - (height // 2)
        voting_window.geometry(f'{width}x{height}+{x}+{y}')

        # Title frame with arcade-style header if in arena mode
        if self.arena_mode:
            title_frame = tk.Frame(voting_window, bg="#000000", bd=5, relief="raised")
            title_frame.pack(fill=tk.X, padx=10, pady=10)
            
            title_label = tk.Label(
                title_frame, 
                text="★ MODEL BATTLE ARENA ★",
                bg="#000000", 
                fg="#00FF00",
                font=("Courier", 16, "bold")
            )
            title_label.pack(pady=10)
            
            subtitle_label = tk.Label(
                title_frame,
                text="RANK THE CHAMPIONS",
                bg="#000000",
                fg="#FF00FF",
                font=("Courier", 12)
            )
            subtitle_label.pack(pady=(0, 10))
        
        list_frame = ttk.Frame(voting_window)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Configure the listbox with arcade theme if in arena mode
        if self.arena_mode:
            list_frame.configure(style="Arcade.TFrame")
            self.style.configure("Arcade.TFrame", background="#000000")

        self.ranking_list = [display_name for _, display_name, _ in self.carousel_images]

        # Configure the listbox with arcade theme if in arena mode
        if self.arena_mode:
            self.listbox = tk.Listbox(
                list_frame, 
                font=("Courier", 12, "bold"),
                height=10,
                bg="#111111",
                fg="#00FF00",
                selectbackground="#00FF00",
                selectforeground="#000000",
                relief="sunken",
                bd=3
            )
        else:
            self.listbox = tk.Listbox(list_frame, font=("Helvetica", 12), height=10)
            
        for item in self.ranking_list:
            self.listbox.insert(tk.END, item)
        self.listbox.pack(fill=tk.BOTH, expand=True)

        # Button frame with arcade theme if in arena mode
        if self.arena_mode:
            button_frame = tk.Frame(voting_window, bg="#000000")
        else:
            button_frame = ttk.Frame(voting_window)
            
        button_frame.pack(fill=tk.X, pady=10)

        # Create buttons with arcade style if in arena mode
        if self.arena_mode:
            up_button = tk.Button(
                button_frame, 
                text="↑ MOVE UP ↑",
                command=self.move_up,
                bg="#00FF00",
                fg="#000000",
                font=("Courier", 12, "bold"),
                relief="raised",
                bd=3
            )
            down_button = tk.Button(
                button_frame, 
                text="↓ MOVE DOWN ↓",
                command=self.move_down,
                bg="#00FF00",
                fg="#000000",
                font=("Courier", 12, "bold"),
                relief="raised",
                bd=3
            )
            submit_button = tk.Button(
                button_frame, 
                text="◆ SUBMIT RANKING ◆",
                command=lambda: self.submit_ranking(voting_window),
                bg="#FF00FF",
                fg="#FFFFFF",
                font=("Courier", 12, "bold"),
                relief="raised",
                bd=3
            )
        else:
            up_button = ttk.Button(button_frame, text="Up", command=self.move_up)
            down_button = ttk.Button(button_frame, text="Down", command=self.move_down)
            submit_button = ttk.Button(button_frame, text="Submit Ranking",
                                   command=lambda: self.submit_ranking(voting_window))
        
        up_button.pack(side=tk.LEFT, padx=10)
        down_button.pack(side=tk.LEFT, padx=10)
        submit_button.pack(side=tk.RIGHT, padx=10)
        
        # Instructions with arcade theme if in arena mode
        if self.arena_mode:
            instructions_frame = tk.Frame(voting_window, bg="#000000")
            instructions_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
            
            instructions = tk.Label(
                instructions_frame,
                text="Select a model and use UP/DOWN to change its ranking.\nCrown your champion by placing it at the top!",
                bg="#000000",
                fg="#00FF00",
                font=("Courier", 10),
                justify=tk.LEFT
            )
            instructions.pack(anchor=tk.W)

    def move_up(self):
        """Move the selected item up in the ranking list"""
        selected = self.listbox.curselection()
        if selected:
            index = selected[0]
            if index > 0:
                item = self.ranking_list.pop(index)
                self.ranking_list.insert(index - 1, item)
                self.update_listbox()
                self.listbox.select_set(index - 1)

    def move_down(self):
        """Move the selected item down in the ranking list"""
        selected = self.listbox.curselection()
        if selected:
            index = selected[0]
            if index < len(self.ranking_list) - 1:
                item = self.ranking_list.pop(index)
                self.ranking_list.insert(index + 1, item)
                self.update_listbox()
                self.listbox.select_set(index + 1)

    def update_listbox(self):
        """Update the listbox with the current ranking list"""
        self.listbox.delete(0, tk.END)
        for item in self.ranking_list:
            self.listbox.insert(tk.END, item)

    def submit_ranking(self, window):
        """Submit the ranking and show the results"""
        ranking = self.ranking_list

        # In Arena Mode, we need to map the display names to the models that created them
        image_to_model = {}
        model_to_id = {}  # Store model_id for each model
        for i, (model_name, model_id) in enumerate(self.get_selected_models()):
            display_name = f"Image {i + 1}"
            image_to_model[display_name] = model_name
            model_to_id[model_name] = model_id

        # Construct the result message
        if self.arena_mode:
            message = "🏆 ARENA BATTLE RESULTS 🏆\n\n"
            for i, item in enumerate(ranking, 1):
                # Get the actual model that generated this image
                model_name = image_to_model.get(item, "Unknown model")
                if i == 1:
                    message += f"🥇 CHAMPION: {model_name}\n"
                elif i == 2:
                    message += f"🥈 RUNNER-UP: {model_name}\n"
                elif i == 3:
                    message += f"🥉 THIRD PLACE: {model_name}\n"
                else:
                    message += f"#{i}: {model_name}\n"
        else:
            message = "Your ranking:\n"
            for i, item in enumerate(ranking, 1):
                # Get the actual model that generated this image
                model_name = image_to_model.get(item, "Unknown model")
                message += f"{i}. {item} - Generated by: {model_name}\n"

        # Store rankings in database
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        session_id = str(uuid.uuid4())

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create voting session
            cursor.execute(
                "INSERT INTO voting_sessions (session_id, user_id, prompt) VALUES (?, ?, ?)",
                (session_id, self.current_user_id, prompt)
            )

            # Store each model's ranking
            for i, item in enumerate(ranking, 1):
                model_name = image_to_model.get(item, "Unknown model")
                model_id = model_to_id.get(model_name, "unknown_model_id")

                ranking_id = str(uuid.uuid4())
                cursor.execute(
                    """INSERT INTO model_rankings 
                       (ranking_id, session_id, model_name, model_id, rank_position) 
                       VALUES (?, ?, ?, ?, ?)""",
                    (ranking_id, session_id, model_name, model_id, i)
                )

            conn.commit()
            self.add_log(f"Rankings saved to database with session ID: {session_id}")

            # Ask if user wants to see the leaderboard
            if self.arena_mode:
                result_dialog = tk.Toplevel(window)
                result_dialog.title("🏆 ARENA RESULTS 🏆")
                result_dialog.geometry("500x400")
                result_dialog.configure(bg="#000000")
                
                # Center dialog
                result_dialog.update_idletasks()
                width = result_dialog.winfo_width()
                height = result_dialog.winfo_height()
                x = (result_dialog.winfo_screenwidth() // 2) - (width // 2)
                y = (result_dialog.winfo_screenheight() // 2) - (height // 2)
                result_dialog.geometry(f'{width}x{height}+{x}+{y}')
                
                # Results frame
                results_frame = tk.Frame(result_dialog, bg="#000000", bd=5, relief="ridge")
                results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
                
                # Title
                title_label = tk.Label(
                    results_frame,
                    text="🏆 THE RESULTS ARE IN! 🏆",
                    font=("Courier", 16, "bold"),
                    bg="#000000",
                    fg="#FFFF00"
                )
                title_label.pack(pady=(20, 30))
                
                # Results text
                results_text = tk.Text(
                    results_frame,
                    font=("Courier", 12),
                    bg="#111111",
                    fg="#00FF00",
                    relief="sunken",
                    bd=3,
                    height=10,
                    width=40
                )
                results_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                results_text.insert(tk.END, message)
                results_text.config(state=tk.DISABLED)
                
                # Button frame
                button_frame = tk.Frame(results_frame, bg="#000000")
                button_frame.pack(fill=tk.X, pady=(20, 10))
                
                # Show leaderboard button
                leaderboard_btn = tk.Button(
                    button_frame,
                    text="VIEW LEADERBOARD",
                    font=("Courier", 12, "bold"),
                    bg="#00FF00",
                    fg="#000000",
                    relief="raised",
                    bd=3,
                    command=lambda: [result_dialog.destroy(), window.destroy(), self.exit_arena_mode(), self.show_leaderboard()]
                )
                leaderboard_btn.pack(side=tk.LEFT, padx=10)
                
                # Close button
                close_btn = tk.Button(
                    button_frame,
                    text="EXIT ARENA",
                    font=("Courier", 12, "bold"),
                    bg="#FF00FF",
                    fg="#FFFFFF",
                    relief="raised",
                    bd=3,
                    command=lambda: [result_dialog.destroy(), window.destroy(), self.exit_arena_mode()]
                )
                close_btn.pack(side=tk.RIGHT, padx=10)
            else:
                show_leaderboard = messagebox.askyesno(
                    "Ranking Submitted",
                    message + "\n\nWould you like to see the current leaderboard?",
                    parent=window
                )

                if show_leaderboard:
                    window.destroy()
                    self.arena_mode = False
                    self.show_leaderboard()
                else:
                    messagebox.showinfo("Ranking Submitted", message, parent=window)
                    window.destroy()
                    self.arena_mode = False

        except sqlite3.Error as e:
            self.add_log(f"Database error while saving rankings: {str(e)}")
            messagebox.showerror("Error", f"Failed to save rankings: {str(e)}", parent=window)
            messagebox.showinfo("Ranking Submitted", message, parent=window)
            window.destroy()
            if self.arena_mode:
                self.exit_arena_mode()
            else:
                self.arena_mode = False
        finally:
            if conn:
                conn.close()

    def re_enable_generate_button(self):
        """Re-enable the generate button and disable the cancel menu item"""
        self.generate_button.config(state=tk.NORMAL)

        menubar = self.root.nametowidget(self.root.cget("menu"))
        file_menu = menubar.nametowidget(menubar.entrycget(0, "menu"))
        file_menu.entryconfigure("Cancel Generation", state=tk.DISABLED)

        self.add_log("Ready for next generation")

    def cancel_generation(self):
        """Cancel all active generations"""
        for model_name, status in self.active_generations.items():
            if status in ["queued", "running"]:
                self.active_generations[model_name] = "canceled"
                self.add_log(f"Canceling generation for {model_name}")

        self.progress_var.set("Canceling all active generations...")
        self.add_log("Canceled all active generations")
        self.re_enable_generate_button()

    def add_to_carousel(self, image, model_name, filepath, identifier=None):
        """Add an image to the carousel collection"""
        existing_indices = [i for i, (_, name, _) in enumerate(self.carousel_images) if name == model_name]

        if existing_indices:
            index = existing_indices[0]
            self.carousel_images[index] = (image, model_name, filepath)

            if self.embedded_current_index == index:
                self.update_embedded_carousel()

            if self.carousel and self.carousel.winfo_exists():
                self.carousel.images[index] = (image, model_name, filepath)
                if self.carousel.current_index == index:
                    self.carousel.update_display()

            self.add_log(f"Updated existing image for {model_name}")
        else:
            self.carousel_images.append((image, model_name, filepath))
            self.embedded_current_index = len(self.carousel_images) - 1
            self.update_embedded_carousel()

            if self.carousel and self.carousel.winfo_exists():
                self.carousel.add_image(image, model_name, filepath)
                self.carousel.current_index = self.embedded_current_index
                self.carousel.update_display()

            self.add_log(f"Added new image for {model_name}")

    def show_carousel(self):
        """Show the image carousel in a fullscreen window"""
        self.show_fullscreen_carousel()

    def on_closing(self):
        """Handle application closing"""
        try:
            if self.carousel and self.carousel.winfo_exists():
                self.carousel.destroy()
            self.executor.shutdown(wait=False)
            self.root.destroy()
        except:
            self.root.destroy()

    def create_embedded_carousel(self):
        """Create an embedded carousel in the main window"""
        carousel_frame = ttk.Frame(self.embedded_carousel_frame)
        carousel_frame.pack(fill=tk.BOTH, expand=True)

        self.embedded_image_frame = ttk.Frame(carousel_frame, height=400)
        self.embedded_image_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        image_bg_frame = ttk.Frame(self.embedded_image_frame, style='ImageBg.TFrame')
        image_bg_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.embedded_image_label = ttk.Label(image_bg_frame, background=self.bg_color)

        self.fullscreen_button = tk.Button(
            image_bg_frame,
            text="⛶",
            bg=self.primary_color,
            fg=self.button_text_color,
            font=('Helvetica', 14),
            relief=tk.RAISED,
            borderwidth=2,
            width=2,
            height=1,
            command=self.show_fullscreen_carousel,
            state=tk.DISABLED
        )
        
        self.gallery_button = tk.Button(
            image_bg_frame,
            text="ℹ",
            bg=self.primary_color,
            fg=self.button_text_color,
            font=('Helvetica', 14),
            relief=tk.RAISED,
            borderwidth=2,
            width=2,
            height=1,
            command=self.view_current_in_gallery,
            state=tk.DISABLED
        )

        nav_frame = ttk.Frame(carousel_frame)
        nav_frame.pack(fill=tk.X, pady=5)

        self.embedded_left_btn = tk.Button(
            nav_frame,
            text="←",
            bg=self.primary_color,
            fg=self.button_text_color,
            font=('Helvetica', 14, 'bold'),
            relief=tk.RAISED,
            borderwidth=2,
            width=2,
            command=self.embedded_prev_image
        )
        self.embedded_left_btn.pack(side=tk.LEFT, padx=10)

        info_frame = ttk.Frame(nav_frame)
        info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.embedded_model_label = ttk.Label(
            info_frame,
            text="No images yet",
            font=("Helvetica", 11, "bold"),
        )
        self.embedded_model_label.pack(anchor=tk.CENTER, pady=2)

        self.embedded_counter_label = ttk.Label(
            info_frame,
            text="",
            font=("Helvetica", 10),
        )
        self.embedded_counter_label.pack(anchor=tk.CENTER)

        self.embedded_right_btn = tk.Button(
            nav_frame,
            text="→",
            bg=self.primary_color,
            fg=self.button_text_color,
            font=('Helvetica', 14, 'bold'),
            relief=tk.RAISED,
            borderwidth=2,
            width=2,
            command=self.embedded_next_image
        )
        self.embedded_right_btn.pack(side=tk.RIGHT, padx=10)

        self.embedded_current_index = 0

    def update_embedded_carousel(self):
        """Update the embedded carousel with the current image"""
        if not self.carousel_images:
            self.embedded_model_label.config(text="No images yet")
            self.embedded_counter_label.config(text="")
            self.fullscreen_button.config(state=tk.DISABLED)
            self.gallery_button.config(state=tk.DISABLED)
            return

        self.fullscreen_button.config(state=tk.NORMAL)
        self.gallery_button.config(state=tk.NORMAL)

        image, model_name, filepath = self.carousel_images[self.embedded_current_index]

        max_width = self.embedded_image_frame.winfo_width() - 40
        max_height = self.embedded_image_frame.winfo_height() - 40

        if max_width <= 0:
            max_width = 500
        if max_height <= 0:
            max_height = 400

        img_width, img_height = image.size
        scale = min(max_width / max(img_width, 1), max_height / max(img_height, 1))

        new_width = int(img_width * scale)
        new_height = int(img_height * scale)

        # Create a copy before modifying
        display_image = image.copy()
        
        # If in arena mode, apply arcade-style borders and effects
        if self.arena_mode:
            # Add a pixelated border
            border_size = 10
            bordered_image = Image.new(
                'RGB', 
                (new_width + 2*border_size, new_height + 2*border_size), 
                "#00FF00"  # Neon green border
            )
            
            # Add image inside border
            resized_image = image.resize((new_width, new_height), Image.LANCZOS)
            bordered_image.paste(resized_image, (border_size, border_size))
            
            # Add pixelated effect to corners
            draw = ImageDraw.Draw(bordered_image)
            
            # Top-left corner
            draw.rectangle((0, 0, border_size//2, border_size//2), fill="#000000")
            draw.rectangle((border_size//2, 0, border_size, border_size//2), fill="#00FF00")
            draw.rectangle((0, border_size//2, border_size//2, border_size), fill="#00FF00")
            
            # Top-right corner
            tr_x = bordered_image.width - border_size
            draw.rectangle((tr_x, 0, tr_x + border_size//2, border_size//2), fill="#00FF00")
            draw.rectangle((tr_x + border_size//2, 0, bordered_image.width, border_size//2), fill="#000000")
            draw.rectangle((tr_x + border_size//2, border_size//2, bordered_image.width, border_size), fill="#00FF00")
            
            # Bottom-left corner
            bl_y = bordered_image.height - border_size
            draw.rectangle((0, bl_y, border_size//2, bl_y + border_size//2), fill="#00FF00")
            draw.rectangle((0, bl_y + border_size//2, border_size//2, bordered_image.height), fill="#000000")
            draw.rectangle((border_size//2, bl_y + border_size//2, border_size, bordered_image.height), fill="#00FF00")
            
            # Bottom-right corner
            br_x = bordered_image.width - border_size
            br_y = bordered_image.height - border_size
            draw.rectangle((br_x, br_y, br_x + border_size//2, br_y + border_size//2), fill="#00FF00")
            draw.rectangle((br_x + border_size//2, br_y, bordered_image.width, br_y + border_size//2), fill="#00FF00")
            draw.rectangle((br_x + border_size//2, br_y + border_size//2, bordered_image.width, bordered_image.height), fill="#000000")
            
            # Use the bordered image
            display_image = bordered_image
        else:
            # Normal display - just resize
            display_image = image.resize((new_width, new_height), Image.LANCZOS)

        tk_image = ImageTk.PhotoImage(display_image)

        self.embedded_image_label.configure(image=tk_image)
        self.embedded_image_label.image = tk_image

        self.embedded_image_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        parent = self.fullscreen_button.master
        parent.update_idletasks()
        self.fullscreen_button.place(relx=1.0, rely=1.0, x=-10, y=-10, anchor=tk.SE)
        self.gallery_button.place(relx=1.0, rely=1.0, x=-50, y=-10, anchor=tk.SE)

        # Update label text based on arena mode
        if self.arena_mode:
            # In arena mode, model name should be hidden
            self.embedded_model_label.config(text=f"CONTENDER #{self.embedded_current_index + 1}")
            self.embedded_counter_label.config(
                text=f"Image {self.embedded_current_index + 1} of {len(self.carousel_images)}")
        else:
            self.embedded_model_label.config(text=f"Model: {model_name}")
            self.embedded_counter_label.config(
                text=f"Image {self.embedded_current_index + 1} of {len(self.carousel_images)}")

        has_prev = self.embedded_current_index > 0
        has_next = self.embedded_current_index < len(self.carousel_images) - 1

        self.embedded_left_btn.config(state=tk.NORMAL if has_prev else tk.DISABLED)
        self.embedded_right_btn.config(state=tk.NORMAL if has_next else tk.DISABLED)
        
    def view_current_in_gallery(self):
        """View the current carousel image in the gallery detail view"""
        if not self.carousel_images:
            return
            
        # Get the current image information
        _, model_name, filepath = self.carousel_images[self.embedded_current_index]
        
        try:
            # Look up the image in the database by filepath
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT image_id FROM images
                WHERE filepath = ? AND model_name = ?
            ''', (filepath, model_name))
            
            result = cursor.fetchone()
            
            if result:
                # If found in the database, show its details
                image_id = result[0]
                self.show_image_details(image_id)
            else:
                # If not found, show a message
                messagebox.showinfo("Image Details", 
                    "This image is not saved in the gallery database yet. Generate new images to add them to the gallery.")
                
        except sqlite3.Error as e:
            self.add_log(f"Database error while finding image: {str(e)}")
        finally:
            if conn:
                conn.close()
                
    def embedded_next_image(self):
        """Show the next image in embedded carousel"""
        if not self.carousel_images or self.embedded_current_index >= len(self.carousel_images) - 1:
            return
            
        self.embedded_current_index += 1
        self.update_embedded_carousel()

    def embedded_prev_image(self):
        """Show the previous image in embedded carousel"""
        if not self.carousel_images or self.embedded_current_index <= 0:
            return

        self.embedded_current_index -= 1
        self.update_embedded_carousel()

    def show_fullscreen_carousel(self):
        """Show the image carousel in a fullscreen window"""
        self.carousel = ImageCarousel(self.root, self.carousel_images)
        self.carousel.title(f"Generated Images - {len(self.carousel_images)} images")

        self.carousel.current_index = self.embedded_current_index
        self.carousel.update_display()

    def show_status_log(self):
        """Show the status log in a separate window"""
        if hasattr(self, 'log_window') and self.log_window.winfo_exists():
            self.log_window.lift()
            return

        self.log_window = tk.Toplevel(self.root)
        self.log_window.title("Status Log")
        self.log_window.geometry("500x400")
        self.log_window.minsize(400, 300)

        self.log_window.update_idletasks()
        width = self.log_window.winfo_width()
        height = self.log_window.winfo_height()
        x = (self.log_window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.log_window.winfo_screenheight() // 2) - (height // 2)
        self.log_window.geometry(f'{width}x{height}+{x}+{y}')

        log_frame = ttk.Frame(self.log_window, padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(log_frame, text="Status Log", font=("Helvetica", 14, "bold")).pack(anchor=tk.W, pady=(0, 10))

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=('Helvetica', 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        if hasattr(self, 'status_text'):
            self.log_text.insert(tk.END, self.status_text.get(1.0, tk.END))

        self.log_text.config(state=tk.DISABLED)

        self.log_window.protocol("WM_DELETE_WINDOW", self.on_log_window_close)

        button_frame = ttk.Frame(log_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        clear_button = ttk.Button(
            button_frame,
            text="Clear Log",
            command=self.clear_log
        )
        clear_button.pack(side=tk.RIGHT)

        close_button = ttk.Button(
            button_frame,
            text="Close",
            command=self.log_window.destroy
        )
        close_button.pack(side=tk.RIGHT, padx=5)

    def on_log_window_close(self):
        """Handle log window closing"""
        if hasattr(self, 'log_window'):
            self.log_window.destroy()
            self.log_window = None

    def clear_log(self):
        """Clear the log contents"""
        if hasattr(self, 'status_text'):
            self.status_text.config(state=tk.NORMAL)
            self.status_text.delete(1.0, tk.END)
            self.status_text.config(state=tk.DISABLED)

        if hasattr(self, 'log_text') and self.log_text.winfo_exists():
            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete(1.0, tk.END)
            self.log_text.config(state=tk.DISABLED)

    def update_images_count(self, delta):
        """Update the number of images per model"""
        new_value = self.images_per_model.get() + delta
        if 1 <= new_value <= 5:
            self.images_per_model.set(new_value)

    def enhance_prompt(self):
        """Enhance the user's prompt using Claude 3.7 Sonnet"""
        original_prompt = self.prompt_text.get("1.0", tk.END).strip()

        if not original_prompt:
            messagebox.showerror("Error", "Please enter a prompt to enhance")
            return

        api_token = self.token_entry.get().strip()

        if not api_token:
            messagebox.showerror("Error", "Please enter your Replicate API token")
            return

        os.environ["REPLICATE_API_TOKEN"] = api_token

        self.progress_var.set("Enhancing prompt...")

        threading.Thread(target=self._enhance_prompt_thread, args=(original_prompt,)).start()

    def _enhance_prompt_thread(self, original_prompt):
        """Run prompt enhancement in a separate thread"""
        try:
            self.root.after(0, lambda: self.add_log(f"Starting prompt enhancement with text: '{original_prompt}'"))

            system_prompt = "You are a creative assistant that helps enhance text prompts for AI image generation."

            user_prompt = f"""
            Here is a user's prompt for AI image generation:
            '{original_prompt}'

            Please enhance this prompt to be more detailed and descriptive. Focus on:
            1. Adding visual details that would help create a better image
            2. Specifying artistic style, lighting, perspective, and composition
            3. Using descriptive adjectives and clear visual language

            Keep the essence and main subject of the original prompt intact.
            Return ONLY the enhanced prompt text with no explanations, introductions, or other text.
            """

            self.root.after(0, lambda: self.add_log("Calling Claude API via Replicate..."))

            output = replicate.run(
                "anthropic/claude-3.7-sonnet",
                input={
                    "system": system_prompt,
                    "prompt": user_prompt,
                    "temperature": 0.7,
                    "max_tokens": 10500
                }
            )

            enhanced_prompt = ""
            if hasattr(output, '__iter__') and not isinstance(output, str):
                for item in output:
                    enhanced_prompt += item
            else:
                enhanced_prompt = str(output)

            if not enhanced_prompt.strip():
                enhanced_prompt = "Could not enhance the prompt. Please try again or use the original prompt."
                self.root.after(0, lambda: self.add_log("Warning: Received empty response from API"))

            self.root.after(0, lambda: self._display_enhanced_prompt(enhanced_prompt))

        except Exception as e:
            error_msg = f"Error enhancing prompt: {str(e)}"
            self.root.after(0, lambda: self.add_log(error_msg))
            self.root.after(0, lambda: self.progress_var.set(""))
            self.root.after(0, lambda: messagebox.showerror("Error", error_msg))

    def _display_enhanced_prompt(self, enhanced_prompt):
        """Display the enhanced prompt in the UI"""
        self.progress_var.set("")

        self.enhanced_prompt_text.delete("1.0", tk.END)
        self.enhanced_prompt_text.insert(tk.END, enhanced_prompt)

        self.enhanced_prompt_frame.pack(fill=tk.X, pady=(5, 0), after=self.prompt_text)

        self.add_log("Prompt enhanced successfully")

    def use_enhanced_prompt(self):
        """Replace the original prompt with the enhanced version"""
        enhanced_prompt = self.enhanced_prompt_text.get("1.0", tk.END).strip()

        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert(tk.END, enhanced_prompt)

        self.enhanced_prompt_frame.pack_forget()

        self.add_log("Enhanced prompt applied")

    def init_database(self):
        """Initialize the SQLite database with necessary tables if they don't exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create voting sessions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS voting_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')

            # Create model rankings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS model_rankings (
                    ranking_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    rank_position INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES voting_sessions (session_id)
                )
            ''')

            # Create images table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS images (
                    image_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    filepath TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')

            # Create anonymous user if not exists
            cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, username)
                VALUES (?, ?)
            ''', ('anonymous', 'Anonymous User'))

            conn.commit()
            self.current_user_id = 'anonymous'
            self.add_log("Database initialized successfully")

        except sqlite3.Error as e:
            self.add_log(f"Database initialization error: {str(e)}")
        finally:
            if conn:
                conn.close()

    def set_username(self):
        """Show a dialog to set the username"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Set Username")
        dialog.geometry("400x180")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (dialog.winfo_screenheight() // 2) - (height // 2)
        dialog.geometry(f'{width}x{height}+{x}+{y}')

        # Content frame
        content_frame = ttk.Frame(dialog, padding=20)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Username label and entry
        ttk.Label(content_frame, text="Enter your username:").pack(anchor=tk.W, pady=(0, 5))

        username_entry = ttk.Entry(content_frame, width=40)
        username_entry.pack(fill=tk.X, pady=(0, 20))

        # Pre-fill with existing username if available
        if self.username != "Anonymous User":
            username_entry.insert(0, self.username)

        # Button frame
        button_frame = ttk.Frame(content_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        # Save button
        save_button = ttk.Button(
            button_frame,
            text="Save",
            command=lambda: self.save_username(username_entry.get(), dialog)
        )
        save_button.pack(side=tk.RIGHT, padx=5)

        # Cancel button
        cancel_button = ttk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy
        )
        cancel_button.pack(side=tk.RIGHT, padx=5)

    def save_username(self, username, dialog):
        """Save the username to the database"""
        if not username.strip():
            messagebox.showerror("Error", "Please enter a valid username", parent=dialog)
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check if user already exists
            cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
            existing_user = cursor.fetchone()

            if existing_user:
                self.current_user_id = existing_user[0]
            else:
                # Create new user
                user_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO users (user_id, username) VALUES (?, ?)",
                    (user_id, username)
                )
                conn.commit()
                self.current_user_id = user_id

            self.username = username
            self.add_log(f"Username set to: {username}")
            dialog.destroy()

        except sqlite3.Error as e:
            self.add_log(f"Database error while setting username: {str(e)}")
            messagebox.showerror("Error", f"Failed to set username: {str(e)}", parent=dialog)
        finally:
            if conn:
                conn.close()

    def show_leaderboard(self):
        """Show the leaderboard of model rankings"""
        try:
            # Get model rankings from database
            model_stats = self.get_model_rankings()

            if not model_stats:
                messagebox.showinfo("Leaderboard", "No ranking data available yet.")
                return

            leaderboard_window = tk.Toplevel(self.root)
            leaderboard_window.title("Model Leaderboard")
            leaderboard_window.geometry("600x500")
            leaderboard_window.minsize(500, 400)

            # Center the window
            leaderboard_window.update_idletasks()
            width = leaderboard_window.winfo_width()
            height = leaderboard_window.winfo_height()
            x = (leaderboard_window.winfo_screenwidth() // 2) - (width // 2)
            y = (leaderboard_window.winfo_screenheight() // 2) - (height // 2)
            leaderboard_window.geometry(f'{width}x{height}+{x}+{y}')

            # Main content frame
            main_frame = ttk.Frame(leaderboard_window, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Title
            ttk.Label(
                main_frame,
                text="AI Model Leaderboard",
                font=("Helvetica", 16, "bold")
            ).pack(pady=(0, 20))

            # Stats frame with scrollbar
            stats_frame = ttk.Frame(main_frame)
            stats_frame.pack(fill=tk.BOTH, expand=True)

            # Create treeview
            columns = ("Rank", "Model", "Score", "First Places", "Total Votes")
            tree = ttk.Treeview(stats_frame, columns=columns, show="headings")

            # Define headings
            for col in columns:
                tree.heading(col, text=col)

            # Set column widths
            tree.column("Rank", width=60, anchor="center")
            tree.column("Model", width=200)
            tree.column("Score", width=80, anchor="center")
            tree.column("First Places", width=100, anchor="center")
            tree.column("Total Votes", width=100, anchor="center")

            # Add scrollbars
            y_scrollbar = ttk.Scrollbar(stats_frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=y_scrollbar.set)

            # Pack scrollbar and treeview
            y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # Add data to treeview
            for i, (model, stats) in enumerate(model_stats.items(), 1):
                tree.insert("", tk.END, values=(
                    i,
                    model,
                    f"{stats['score']:.2f}",
                    stats['first_places'],
                    stats['total_votes']
                ))

            # Button frame
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=(20, 0))

            # Advanced stats button
            advanced_button = ttk.Button(
                button_frame,
                text="Advanced Statistics",
                command=lambda: self.show_advanced_statistics()
            )
            advanced_button.pack(side=tk.LEFT)

            # Close button
            close_button = ttk.Button(
                button_frame,
                text="Close",
                command=leaderboard_window.destroy
            )
            close_button.pack(side=tk.RIGHT)

            # Refresh button
            refresh_button = ttk.Button(
                button_frame,
                text="Refresh Data",
                command=lambda: self.refresh_leaderboard(tree)
            )
            refresh_button.pack(side=tk.RIGHT, padx=10)

        except Exception as e:
            self.add_log(f"Error showing leaderboard: {str(e)}")
            messagebox.showerror("Error", f"Failed to show leaderboard: {str(e)}")

    def refresh_leaderboard(self, tree):
        """Refresh the leaderboard data"""
        try:
            # Clear existing data
            for item in tree.get_children():
                tree.delete(item)

            # Get updated model rankings
            model_stats = self.get_model_rankings()

            # Add data to treeview
            for i, (model, stats) in enumerate(model_stats.items(), 1):
                tree.insert("", tk.END, values=(
                    i,
                    model,
                    f"{stats['score']:.2f}",
                    stats['first_places'],
                    stats['total_votes']
                ))
        except Exception as e:
            self.add_log(f"Error refreshing leaderboard: {str(e)}")
            messagebox.showerror("Error", f"Failed to refresh leaderboard: {str(e)}")

    def get_model_rankings(self):
        """Get aggregated model rankings from the database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get all rankings
            cursor.execute("""
                SELECT model_name, rank_position 
                FROM model_rankings
                ORDER BY session_id, rank_position
            """)
            rankings = cursor.fetchall()

            if not rankings:
                return {}

            # Process rankings into a scoring system
            model_stats = {}

            for model_name, rank in rankings:
                if model_name not in model_stats:
                    model_stats[model_name] = {
                        'total_votes': 0,
                        'sum_rank': 0,
                        'first_places': 0,
                        'score': 0
                    }

                model_stats[model_name]['total_votes'] += 1
                model_stats[model_name]['sum_rank'] += rank

                if rank == 1:
                    model_stats[model_name]['first_places'] += 1

            # Calculate score (inverse of average rank, so lower ranks = higher score)
            for model in model_stats:
                avg_rank = model_stats[model]['sum_rank'] / model_stats[model]['total_votes']
                # Score formula: 10 - avg_rank with bonus for first places
                first_place_bonus = model_stats[model]['first_places'] / model_stats[model]['total_votes'] * 2
                model_stats[model]['score'] = (10 - avg_rank) + first_place_bonus

            # Sort by score in descending order
            return dict(sorted(model_stats.items(), key=lambda x: x[1]['score'], reverse=True))

        except sqlite3.Error as e:
            self.add_log(f"Database error while getting rankings: {str(e)}")
            return {}
        finally:
            if conn:
                conn.close()

    def show_advanced_statistics(self):
        """Show advanced statistics and analytics from the ranking data"""
        try:
            # Fetch all the ranking data
            conn = sqlite3.connect(self.db_path)

            # Get all sessions with user info
            sessions_df = pd.read_sql_query("""
                SELECT vs.session_id, vs.prompt, vs.created_at, u.username
                FROM voting_sessions vs
                JOIN users u ON vs.user_id = u.user_id
                ORDER BY vs.created_at DESC
            """, conn)

            # Get all rankings
            rankings_df = pd.read_sql_query("""
                SELECT mr.session_id, mr.model_name, mr.rank_position,
                       vs.created_at, u.username
                FROM model_rankings mr
                JOIN voting_sessions vs ON mr.session_id = vs.session_id
                JOIN users u ON vs.user_id = u.user_id
                ORDER BY vs.created_at DESC
            """, conn)

            if rankings_df.empty:
                messagebox.showinfo("Statistics", "No ranking data available yet.")
                return

            # Create statistics window
            stats_window = tk.Toplevel(self.root)
            stats_window.title("Advanced Model Statistics")
            stats_window.geometry("800x600")
            stats_window.minsize(700, 500)

            # Center the window
            stats_window.update_idletasks()
            width = stats_window.winfo_width()
            height = stats_window.winfo_height()
            x = (stats_window.winfo_screenwidth() // 2) - (width // 2)
            y = (stats_window.winfo_screenheight() // 2) - (height // 2)
            stats_window.geometry(f'{width}x{height}+{x}+{y}')

            # Main notebook for tabs
            notebook = ttk.Notebook(stats_window)
            notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Summary tab
            summary_frame = ttk.Frame(notebook, padding=10)
            notebook.add(summary_frame, text="Summary")

            # Summary statistics
            ttk.Label(
                summary_frame,
                text="Model Ranking Statistics",
                font=("Helvetica", 16, "bold")
            ).pack(pady=(0, 20))

            # Total sessions and users
            total_sessions = len(sessions_df)
            total_users = len(sessions_df['username'].unique())

            stats_text = f"Total Voting Sessions: {total_sessions}\n"
            stats_text += f"Total Unique Users: {total_users}\n"
            stats_text += f"Total Rankings Submitted: {len(rankings_df)}\n\n"

            # Most popular models
            popular_models = rankings_df['model_name'].value_counts().head(5)
            stats_text += "Most Frequently Voted Models:\n"
            for model, count in popular_models.items():
                stats_text += f"- {model}: {count} votes\n"

            stats_text += "\nTop Ranked Models (Average Position):\n"
            avg_ranks = rankings_df.groupby('model_name')['rank_position'].mean().sort_values()
            for model, avg_rank in avg_ranks.head(5).items():
                stats_text += f"- {model}: {avg_rank:.2f} average position\n"

            stats_text_widget = scrolledtext.ScrolledText(
                summary_frame,
                wrap=tk.WORD,
                width=70,
                height=20,
                font=('Helvetica', 11)
            )
            stats_text_widget.pack(fill=tk.BOTH, expand=True, pady=10)
            stats_text_widget.insert(tk.END, stats_text)
            stats_text_widget.config(state=tk.DISABLED)

            # Export data button
            button_frame = ttk.Frame(stats_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            export_button = ttk.Button(
                button_frame,
                text="Export Statistics",
                command=lambda: self.export_statistics(rankings_df, sessions_df)
            )
            export_button.pack(side=tk.LEFT)

            close_button = ttk.Button(
                button_frame,
                text="Close",
                command=stats_window.destroy
            )
            close_button.pack(side=tk.RIGHT)

        except Exception as e:
            self.add_log(f"Error showing advanced statistics: {str(e)}")
            messagebox.showerror("Error", f"Failed to show statistics: {str(e)}")
        finally:
            if conn:
                conn.close()

    def export_statistics(self, rankings_df, sessions_df):
        """Export statistics data to CSV files"""
        try:
            # Create export directory if it doesn't exist
            export_dir = os.path.join(self.output_dir, "statistics")
            if not os.path.exists(export_dir):
                os.makedirs(export_dir)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Export rankings
            rankings_path = os.path.join(export_dir, f"rankings_{timestamp}.csv")
            rankings_df.to_csv(rankings_path, index=False)

            # Export sessions
            sessions_path = os.path.join(export_dir, f"sessions_{timestamp}.csv")
            sessions_df.to_csv(sessions_path, index=False)

            # Generate summary stats
            summary_stats = pd.DataFrame({
                'model': rankings_df['model_name'].unique()
            })

            # Calculate stats for each model
            stats_data = []
            for model in summary_stats['model']:
                model_data = rankings_df[rankings_df['model_name'] == model]
                stats_data.append({
                    'model': model,
                    'avg_rank': model_data['rank_position'].mean(),
                    'total_votes': len(model_data),
                    'first_places': len(model_data[model_data['rank_position'] == 1]),
                    'score': 10 - model_data['rank_position'].mean() +
                             (len(model_data[model_data['rank_position'] == 1]) /
                              len(model_data) * 2 if len(model_data) > 0 else 0)
                })

            # Create summary dataframe
            summary_df = pd.DataFrame(stats_data)
            summary_df = summary_df.sort_values('score', ascending=False)

            # Export summary
            summary_path = os.path.join(export_dir, f"model_summary_{timestamp}.csv")
            summary_df.to_csv(summary_path, index=False)

            messagebox.showinfo(
                "Export Complete",
                f"Statistics exported to:\n{export_dir}"
            )

        except Exception as e:
            self.add_log(f"Error exporting statistics: {str(e)}")
            messagebox.showerror("Error", f"Failed to export statistics: {str(e)}")

    def _run_model_with_timeout(self, model_id, prompt, generation_name):
        """Run a model with input and store the result for the generation thread"""
        try:
            if not hasattr(self, 'thread_results'):
                self.thread_results = {}
                
            result = replicate.run(
                model_id,
                input={"prompt": prompt}
            )
            
            # Store result if generation hasn't been canceled
            if self.active_generations.get(generation_name) != "canceled":
                self.thread_results[generation_name] = result
        except Exception as e:
            self.add_log(f"Error in model execution thread: {str(e)}")

    def show_gallery(self):
        """Show the gallery of all generated images"""
        try:
            # Get all images from database and from the output directory
            all_images = self.get_gallery_images()
            
            if not all_images:
                self.add_log("No images found in gallery")
                messagebox.showinfo("Gallery Empty", "No images found in the gallery")
                return
            
            # Create gallery window
            gallery_window = tk.Toplevel(self.root)
            gallery_window.title("Image Gallery")
            gallery_window.geometry("900x600")
            gallery_window.minsize(600, 400)
            
            # Create frame for filter options
            filter_frame = ttk.Frame(gallery_window)
            filter_frame.pack(fill=tk.X, padx=10, pady=5)
            
            # Label for filter
            ttk.Label(filter_frame, text="Filter by model:").pack(side=tk.LEFT, padx=5)
            
            # Get unique model names from all images
            model_names = sorted(set(image[3] for image in all_images if image[3]))
            model_names.insert(0, "All Models")  # Add option to show all models
            
            # Variable to store selected model
            selected_model = tk.StringVar(value="All Models")
            
            # Create dropdown for model selection
            model_dropdown = ttk.Combobox(filter_frame, textvariable=selected_model, values=model_names, state="readonly")
            model_dropdown.pack(side=tk.LEFT, padx=5)
            
            # Label to show count of displayed images
            image_count_var = tk.StringVar(value=f"Showing {len(all_images)} images")
            ttk.Label(filter_frame, textvariable=image_count_var).pack(side=tk.RIGHT, padx=10)
            
            # Create canvas for scrolling
            canvas = tk.Canvas(gallery_window)
            scrollbar = ttk.Scrollbar(gallery_window, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Pack canvas and scrollbar
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # Frame for the grid of images
            grid_frame = ttk.Frame(scrollable_frame)
            grid_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Store references to prevent garbage collection
            self.thumbnail_refs = []
            
            # Function to update gallery based on filter
            def update_gallery(*args):
                # Clear previous images
                for widget in grid_frame.winfo_children():
                    widget.destroy()
                
                self.thumbnail_refs.clear()
                
                # Filter images based on selected model
                selected = selected_model.get()
                filtered_images = all_images if selected == "All Models" else [img for img in all_images if img[3] == selected]
                
                # Update count
                image_count_var.set(f"Showing {len(filtered_images)} images")
                
                # Number of columns in the grid
                num_columns = 4
                
                # Display images in grid
                for i, (image_id, filepath, prompt, model_name, created_at) in enumerate(filtered_images):
                    row = i // num_columns
                    col = i % num_columns
                    
                    # Create frame for each image
                    img_frame = ttk.Frame(grid_frame, padding=5)
                    img_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
                    
                    try:
                        # Open and resize image for thumbnail
                        img = Image.open(filepath)
                        img.thumbnail((200, 200))
                        photo = ImageTk.PhotoImage(img)
                        self.thumbnail_refs.append(photo)  # Keep reference
                        
                        # Create image label
                        img_label = ttk.Label(img_frame, image=photo)
                        img_label.pack(fill="both", expand=True)
                        
                        # Add click event to show details
                        img_label.bind("<Button-1>", lambda e, id=image_id: self.show_image_details(id))
                        
                        # Add caption with truncated prompt
                        if prompt:
                            caption = prompt[:25] + "..." if len(prompt) > 25 else prompt
                            ttk.Label(img_frame, text=caption).pack()
                        
                        # Add model name if available
                        if model_name:
                            ttk.Label(img_frame, text=f"Model: {model_name}").pack()
                    
                    except Exception as e:
                        ttk.Label(img_frame, text="Error loading image").pack()
                        self.add_log(f"Error loading image thumbnail: {str(e)}")
            
            # Bind the update function to the dropdown
            selected_model.trace_add("write", update_gallery)
            
            # Initial display
            update_gallery()
            
        except Exception as e:
            self.add_log(f"Error showing gallery: {str(e)}")
            messagebox.showerror("Error", f"Could not show gallery: {str(e)}")

    def get_gallery_images(self):
        """Get all images from the database and from the output directory"""
        all_images = []
        try:
            # First get images from database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT image_id, filepath, prompt, model_name, created_at
                FROM images
                ORDER BY created_at DESC
            ''')
            
            db_images = {filepath: (image_id, filepath, prompt, model_name, created_at) 
                        for image_id, filepath, prompt, model_name, created_at in cursor.fetchall()}
            
            # Add database images to the results
            all_images.extend(list(db_images.values()))
            
            # Then scan the output directory for any images not in the database
            for root, dirs, files in os.walk(self.output_dir):
                for file in files:
                    if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                        filepath = os.path.join(root, file)
                        
                        # Skip if already added from database
                        if filepath in db_images:
                            continue
                        
                        # Extract model name from the directory structure
                        model_dir = os.path.basename(root)
                        model_name = model_dir.replace("_", " ")
                        
                        # Create a placeholder image ID
                        image_id = f"file_{uuid.uuid4()}"
                        
                        # Try to extract prompt from filename (if using our naming convention)
                        filename_parts = os.path.splitext(file)[0].split('_')
                        if len(filename_parts) > 1:
                            # Last part is likely the timestamp, join the rest for the prompt
                            prompt = " ".join(filename_parts[:-1]).replace("_", " ")
                        else:
                            prompt = "Unknown prompt"
                            
                        # Get file creation time
                        try:
                            created_at = datetime.fromtimestamp(os.path.getctime(filepath)).strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            created_at = "Unknown"
                            
                        # Add to results
                        all_images.append((image_id, filepath, prompt, model_name, created_at))
            
            # Sort all images by creation time (newest first)
            all_images.sort(key=lambda x: x[4] if x[4] != "Unknown" else "", reverse=True)
            
            return all_images
            
        except sqlite3.Error as e:
            self.add_log(f"Database error while getting gallery images: {str(e)}")
            return []
        except Exception as e:
            self.add_log(f"Error scanning image directory: {str(e)}")
            return []
        finally:
            if conn:
                conn.close()
                
    def show_image_details(self, image_id):
        """Show details of a specific image"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT image_id, filepath, prompt, model_name, model_id, created_at
                FROM images
                WHERE image_id = ?
            ''', (image_id,))
            
            image_data = cursor.fetchone()
            
            if not image_data:
                messagebox.showerror("Error", "Image not found in database.")
                return
                
            image_id, filepath, prompt, model_name, model_id, created_at = image_data
            
            # Create image details window
            details_window = tk.Toplevel(self.root)
            details_window.title(f"Image by {model_name}")
            details_window.geometry("800x600")
            details_window.minsize(600, 500)
            
            # Center the window
            details_window.update_idletasks()
            width = details_window.winfo_width()
            height = details_window.winfo_height()
            x = (details_window.winfo_screenwidth() // 2) - (width // 2)
            y = (details_window.winfo_screenheight() // 2) - (height // 2)
            details_window.geometry(f'{width}x{height}+{x}+{y}')
            
            # Main content frame
            main_frame = ttk.Frame(details_window, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Image frame
            image_frame = ttk.Frame(main_frame, style='ImageBg.TFrame')
            image_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
            
            try:
                # Load the image
                pil_image = Image.open(filepath)
                
                # Calculate scaled size to fit window while maintaining aspect ratio
                max_width = 700
                max_height = 400
                img_width, img_height = pil_image.size
                scale = min(max_width / img_width, max_height / img_height)
                new_width = int(img_width * scale)
                new_height = int(img_height * scale)
                
                # Resize the image
                resized_image = pil_image.resize((new_width, new_height), Image.LANCZOS)
                img = ImageTk.PhotoImage(resized_image)
                
                # Keep a reference to prevent garbage collection
                self.detail_image = img
                
                # Image label
                img_label = ttk.Label(image_frame, image=img, background='white')
                img_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
                
            except Exception as e:
                error_msg = f"Error loading image: {str(e)}"
                self.add_log(error_msg)
                ttk.Label(image_frame, text=error_msg).pack(pady=50)
            
            # Details frame
            details_frame = ttk.Frame(main_frame)
            details_frame.pack(fill=tk.X, pady=(0, 20))
            
            # Details grid
            ttk.Label(details_frame, text="Model:", font=("Helvetica", 11, "bold")).grid(
                row=0, column=0, sticky=tk.W, padx=(0, 10), pady=5)
            ttk.Label(details_frame, text=model_name).grid(
                row=0, column=1, sticky=tk.W, pady=5)
                
            ttk.Label(details_frame, text="Prompt:", font=("Helvetica", 11, "bold")).grid(
                row=1, column=0, sticky=tk.W, padx=(0, 10), pady=5)
                
            # Prompt text with wrapping
            prompt_text = scrolledtext.ScrolledText(
                details_frame, 
                height=4, 
                width=60, 
                wrap=tk.WORD,
                font=("Helvetica", 10)
            )
            prompt_text.grid(row=1, column=1, sticky=tk.W, pady=5)
            prompt_text.insert(tk.END, prompt)
            prompt_text.config(state=tk.DISABLED)
            
            ttk.Label(details_frame, text="Created:", font=("Helvetica", 11, "bold")).grid(
                row=2, column=0, sticky=tk.W, padx=(0, 10), pady=5)
            ttk.Label(details_frame, text=created_at).grid(
                row=2, column=1, sticky=tk.W, pady=5)
            
            # Configure grid to expand properly
            details_frame.columnconfigure(1, weight=1)
            
            # Button frame
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=(10, 0))
            
            # Use prompt button
            use_prompt_btn = ttk.Button(
                button_frame,
                text="Use This Prompt",
                command=lambda: self.use_gallery_prompt(prompt, details_window)
            )
            use_prompt_btn.pack(side=tk.LEFT)
            
            # Close button
            close_button = ttk.Button(
                button_frame,
                text="Close",
                command=details_window.destroy
            )
            close_button.pack(side=tk.RIGHT)
            
        except sqlite3.Error as e:
            self.add_log(f"Database error while getting image details: {str(e)}")
            messagebox.showerror("Error", f"Failed to get image details: {str(e)}")
        except Exception as e:
            self.add_log(f"Error showing image details: {str(e)}")
            messagebox.showerror("Error", f"Failed to show image details: {str(e)}")
        finally:
            if conn:
                conn.close()
                
    def use_gallery_prompt(self, prompt, details_window=None):
        """Use the prompt from a gallery image"""
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert(tk.END, prompt)
        self.add_log(f"Using prompt from gallery: {prompt[:50]}...")
        
        if details_window:
            details_window.destroy()


class MultiSelectDropdown(ttk.Frame):
    """A custom dropdown widget that allows multiple selections"""

    def __init__(self, parent, options=None, width=30, placeholder="Select items...",
                 bg_color="#FFFFFF", select_color="#4285f4", **kwargs):
        super().__init__(parent, **kwargs)

        self.parent = parent
        self.options = options or []
        self.width = width
        self.placeholder = placeholder
        self.bg_color = bg_color
        self.select_color = select_color

        self.is_open = False
        self.selected = {}

        for option in self.options:
            self.selected[option] = False

        self.dropdown_button = tk.Button(
            self,
            text=self.placeholder,
            relief=tk.GROOVE,
            bg="white",
            anchor=tk.W,
            padx=8,
            pady=4,
            width=width,
            command=self.toggle_dropdown,
            highlightthickness=1,
            highlightcolor="#CCCCCC"
        )
        self.dropdown_button.pack(fill=tk.X)

        self.dropdown_window = None

        self.bind("<FocusOut>", self.on_focus_out)

    def toggle_dropdown(self):
        """Toggle the dropdown visibility"""
        if self.is_open:
            self.close_dropdown()
        else:
            self.open_dropdown()

    def open_dropdown(self):
        """Open the dropdown"""
        if self.is_open:
            return

        self.is_open = True

        x = self.dropdown_button.winfo_rootx()
        y = self.dropdown_button.winfo_rooty() + self.dropdown_button.winfo_height()
        width = self.dropdown_button.winfo_width()

        self.dropdown_window = tk.Toplevel(self)
        self.dropdown_window.wm_overrideredirect(True)
        self.dropdown_window.geometry(f"{width}x{min(len(self.options) * 30, 200)}+{x}+{y}")
        self.dropdown_window.configure(bg="white", highlightthickness=1, highlightbackground="#CCCCCC")

        canvas_frame = ttk.Frame(self.dropdown_window)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(canvas_frame, bg="white", bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        options_frame = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=options_frame, anchor=tk.NW, width=width - scrollbar.winfo_reqwidth())

        self.option_vars = {}
        for i, option in enumerate(self.options):
            var = tk.BooleanVar(value=self.selected[option])
            self.option_vars[option] = var

            option_frame = ttk.Frame(options_frame)
            option_frame.pack(fill=tk.X)

            option_frame.bind("<Enter>", lambda e, f=option_frame: f.configure(style="Hover.TFrame"))
            option_frame.bind("<Leave>", lambda e, f=option_frame: f.configure(style="TFrame"))

            cb = ttk.Checkbutton(
                option_frame,
                text=option,
                variable=var,
                command=lambda o=option: self.on_option_click(o),
                style="MultiSelect.TCheckbutton"
            )
            cb.pack(side=tk.LEFT, padx=5, pady=3, fill=tk.X, expand=True)

        options_frame.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

        self.dropdown_window.bind("<FocusOut>", self.on_focus_out)
        self.dropdown_window.bind("<ButtonPress-1>", self.on_button_press)

        self.dropdown_window.focus_set()

        self.style = ttk.Style()
        self.style.configure("Hover.TFrame", background="#F0F0F0")
        self.style.configure("MultiSelect.TCheckbutton", background="white")

    def close_dropdown(self):
        """Close the dropdown"""
        if not self.is_open:
            return

        self.is_open = False
        if self.dropdown_window:
            self.dropdown_window.destroy()
            self.dropdown_window = None

        self.update_button_text()

    def on_option_click(self, option):
        """Handle option click"""
        self.selected[option] = self.option_vars[option].get()
        self.update_button_text()

    def update_button_text(self):
        """Update the dropdown button to reflect selected items"""
        selected_items = [option for option, selected in self.selected.items() if selected]

        if not selected_items:
            self.dropdown_button.config(text=self.placeholder)
        elif len(selected_items) == 1:
            self.dropdown_button.config(text=selected_items[0])
        else:
            self.dropdown_button.config(text=f"{len(selected_items)} models selected")

    def on_focus_out(self, event):
        """Close dropdown when focus is lost"""
        if self.is_open and self.dropdown_window and not self.dropdown_window.focus_get():
            self.close_dropdown()

    def on_button_press(self, event):
        """Track button presses to handle outside clicks"""
        if not (0 <= event.x < self.dropdown_window.winfo_width() and
                0 <= event.y < self.dropdown_window.winfo_height()):
            self.close_dropdown()

    def get_selected(self):
        """Get the list of selected items"""
        return [option for option, selected in self.selected.items() if selected]

    def select_item(self, item):
        """Select a specific item"""
        if item in self.selected:
            self.selected[item] = True
            if hasattr(self, 'option_vars') and item in self.option_vars:
                self.option_vars[item].set(True)
            self.update_button_text()

    def deselect_item(self, item):
        """Deselect a specific item"""
        if item in self.selected:
            self.selected[item] = False
            if hasattr(self, 'option_vars') and item in self.option_vars:
                self.option_vars[item].set(False)
            self.update_button_text()

    def select_all(self):
        """Select all items"""
        for option in self.options:
            self.selected[option] = True
            if hasattr(self, 'option_vars') and option in self.option_vars:
                self.option_vars[option].set(True)
        self.update_button_text()

    def deselect_all(self):
        """Deselect all items"""
        for option in self.options:
            self.selected[option] = False
            if hasattr(self, 'option_vars') and option in self.option_vars:
                self.option_vars[option].set(False)
            self.update_button_text()


if __name__ == "__main__":
    root = tk.Tk()
    app = ImageGeneratorApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
    root.mainloop()