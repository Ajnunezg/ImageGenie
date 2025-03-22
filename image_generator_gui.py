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
        
        # Configure colors
        self.primary_color = "#4285f4"  # Google blue
        self.bg_color = "#f0f0f0"
        self.accent_color = "#fbbc05"  # Google yellow
        
        self.style.configure('TFrame', background=self.bg_color)
        self.style.configure('TLabel', background=self.bg_color, font=('Helvetica', 12))
        self.style.configure('TEntry', font=('Helvetica', 12))
        self.style.configure('TButton', 
                             font=('Helvetica', 12, 'bold'),
                             background=self.primary_color,
                             foreground='white')
        
        # Available models dictionary with name and ID
        self.available_models = {
            "Flux Schnell": "black-forest-labs/flux-schnell",
            "Recraft-v3": "recraft-ai/recraft-v3",
            "Imagen 3": "google/imagen-3",
            "Ideogram-v2a-turbo": "ideogram-ai/ideogram-v2a-turbo",
            "Nvidia Sana": "nvidia/sana:c6b5d2b7459910fec94432e9e1203c3cdce92d6db20f714f1355747990b52fa6"
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
        
        # Image carousel reference
        self.carousel = None
        self.carousel_images = []
        
        self.create_widgets()
        self.load_saved_token()
        
    def create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Title
        title_label = ttk.Label(main_frame, text="AI Image Generator", font=('Helvetica', 16, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # Left panel for controls
        left_panel = ttk.Frame(main_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # Right panel for image display
        self.right_panel = ttk.Frame(main_frame)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Add a canvas with scrollbar for the image display
        self.canvas_frame = ttk.Frame(self.right_panel)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg=self.bg_color)
        self.scrollbar = ttk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.image_frame = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.image_frame, anchor=tk.NW)
        
        self.image_frame.bind("<Configure>", self._configure_image_frame)
        
        # API Token frame
        token_frame = ttk.Frame(left_panel)
        token_frame.pack(fill=tk.X, pady=10)
        
        token_label = ttk.Label(token_frame, text="Replicate API Token:")
        token_label.pack(anchor=tk.W)
        
        self.token_entry = ttk.Entry(token_frame, width=30, show="•")
        self.token_entry.pack(fill=tk.X, pady=5)
        
        # Save token checkbox
        self.save_token_var = tk.BooleanVar(value=False)
        save_token_cb = ttk.Checkbutton(
            token_frame,
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
        
        prompt_label = ttk.Label(prompt_frame, text="Image Prompt:")
        prompt_label.pack(anchor=tk.W)
        
        self.prompt_text = scrolledtext.ScrolledText(prompt_frame, height=4, width=30, wrap=tk.WORD,
                                  font=('Helvetica', 10))
        self.prompt_text.pack(fill=tk.X, pady=5)
        self.prompt_text.insert(tk.END, "an iguana on the beach, pointillism")
        
        # Model selection frame
        model_frame = ttk.Frame(left_panel)
        model_frame.pack(fill=tk.X, pady=10)
        
        model_label = ttk.Label(model_frame, text="Select Models:")
        model_label.pack(anchor=tk.W)
        
        # Create checkboxes for model selection
        self.model_vars = {}
        for model_name in self.available_models.keys():
            var = tk.BooleanVar(value=False)
            self.model_vars[model_name] = var
            cb = ttk.Checkbutton(model_frame, text=model_name, variable=var)
            cb.pack(anchor=tk.W, padx=10)
        
        # Select the first model by default
        first_model = list(self.available_models.keys())[0]
        self.model_vars[first_model].set(True)
        
        # Advanced options frame (collapsible)
        self.advanced_frame = ttk.Frame(left_panel)
        self.advanced_frame.pack(fill=tk.X, pady=5)
        
        # Create a toggle button for advanced options
        self.show_advanced = tk.BooleanVar(value=False)
        self.advanced_toggle = ttk.Checkbutton(
            self.advanced_frame, 
            text="Show Advanced Options",
            variable=self.show_advanced,
            command=self.toggle_advanced_options
        )
        self.advanced_toggle.pack(anchor=tk.W)
        
        # Create frame for advanced options (initially hidden)
        self.advanced_options = ttk.Frame(left_panel)
        
        # Custom model ID entry
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
        
        # Timeout setting
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
            fg="white",
            font=('Helvetica', 11, 'bold'),
            relief=tk.FLAT,
            padx=15,
            pady=8,
            command=self.generate_images
        )
        self.generate_button.pack(pady=10)
        
        # Cancel button
        self.cancel_button = tk.Button(
            button_frame,
            text="Cancel Generation",
            bg="#ea4335",  # Google red
            fg="white",
            font=('Helvetica', 11, 'bold'),
            relief=tk.FLAT,
            padx=15,
            pady=8,
            command=self.cancel_generation,
            state=tk.DISABLED
        )
        self.cancel_button.pack(pady=5)
        
        # Progress indicator
        self.progress_var = tk.StringVar(value="")
        self.progress_label = ttk.Label(button_frame, textvariable=self.progress_var)
        self.progress_label.pack(pady=5)
        
        # Status log
        status_frame = ttk.Frame(left_panel)
        status_frame.pack(fill=tk.X, pady=10)
        
        status_label = ttk.Label(status_frame, text="Status Log:")
        status_label.pack(anchor=tk.W)
        
        self.status_text = scrolledtext.ScrolledText(status_frame, height=8, width=30, wrap=tk.WORD,
                                   font=('Helvetica', 9))
        self.status_text.pack(fill=tk.X, pady=5)
        self.status_text.config(state=tk.DISABLED)
    
    def _configure_image_frame(self, event):
        # Update the scrollregion to encompass the inner frame
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def toggle_advanced_options(self):
        if self.show_advanced.get():
            self.advanced_options.pack(fill=tk.X, pady=5, after=self.advanced_frame)
        else:
            self.advanced_options.pack_forget()
    
    def get_selected_models(self):
        selected_models = []
        
        # Check if custom model is selected
        if self.show_advanced.get() and self.use_custom_model.get():
            custom_model = self.custom_model_entry.get().strip()
            if custom_model:
                return [("Custom Model", custom_model)]
        
        # Get all selected models from checkboxes
        for model_name, var in self.model_vars.items():
            if var.get():
                model_id = self.available_models[model_name]
                selected_models.append((model_name, model_id))
        
        return selected_models
    
    def add_log(self, message):
        self.status_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
    
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
            
            self.add_log("API token saved successfully")
        except Exception as e:
            self.add_log(f"Error saving API token: {str(e)}")
    
    def load_saved_token(self):
        """Load the saved API token if available"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                
                if 'api_token' in settings and settings['api_token']:
                    self.token_entry.delete(0, tk.END)
                    self.token_entry.insert(0, settings['api_token'])
                    self.save_token_var.set(True)
                    self.add_log("Loaded saved API token")
        except Exception as e:
            self.add_log(f"Error loading saved API token: {str(e)}")
    
    def generate_images(self):
        # Get API token and prompt
        api_token = self.token_entry.get().strip()
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        selected_models = self.get_selected_models()
        
        # Save token if checkbox is selected
        if self.save_token_var.get() and api_token:
            self.save_token_to_file(api_token)
        
        # Input validation
        if not api_token:
            messagebox.showerror("Error", "Please enter your Replicate API token")
            return
        
        if not prompt:
            messagebox.showerror("Error", "Please enter an image prompt")
            return
        
        if not selected_models:
            messagebox.showerror("Error", "Please select at least one model")
            return
        
        # Get timeout value from advanced settings
        try:
            self.generation_timeout = int(self.timeout_var.get())
            if self.generation_timeout < 10:
                self.generation_timeout = 10  # Minimum 10 seconds
                self.timeout_var.set("10")
        except ValueError:
            self.generation_timeout = 180  # Default to 3 minutes
            self.timeout_var.set("180")
        
        # Disable generate button, enable cancel button
        self.generate_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        self.progress_var.set(f"Generating images with {len(selected_models)} model(s)...")
        self.add_log(f"Starting generation with prompt: {prompt[:50]}{'...' if len(prompt) > 50 else ''}")
        
        # Reset carousel images
        self.carousel_images = []
        
        # Reset active generations tracking
        self.active_generations = {}
        
        # Store the API token in environment
        os.environ["REPLICATE_API_TOKEN"] = api_token
        
        # Create a tracker for completion
        generation_complete = threading.Event()
        
        # Submit tasks to thread pool executor for each model
        futures = []
        for idx, (model_name, model_id) in enumerate(selected_models):
            self.add_log(f"Queuing model: {model_name}")
            self.active_generations[model_name] = "queued"
            
            future = self.executor.submit(
                self._generate_image_thread, 
                api_token, 
                prompt, 
                model_name, 
                model_id, 
                idx,
                generation_complete
            )
            futures.append(future)
        
        # Start a watchdog timer to check on threads and re-enable button after timeout
        self.root.after(1000, self._check_generation_status, futures, generation_complete)
    
    def _generate_image_thread(self, api_token, prompt, model_name, model_id, position, complete_event):
        try:
            self.root.after(0, lambda: self.add_log(f"Starting generation with {model_name}..."))
            self.active_generations[model_name] = "running"
            
            # Run model with timeout
            output = replicate.run(
                model_id,
                input={"prompt": prompt}
            )
            
            # If generation was canceled
            if self.active_generations.get(model_name) == "canceled":
                self.root.after(0, lambda: self.add_log(f"Generation with {model_name} was canceled"))
                return
            
            # Download and display image
            # Different models may return results in different formats
            if not output:  # Handle empty output case
                raise ValueError("Model returned empty result")
                
            image_url = output[0] if isinstance(output, list) else output
            
            self.root.after(0, lambda: self.add_log(f"Downloading image from {model_name}..."))
            
            response = requests.get(image_url, timeout=30)  # 30 second timeout for download
            if response.status_code == 200:
                image_data = response.content
                
                # Create model-specific directory if it doesn't exist
                model_dir = os.path.join(self.output_dir, model_name.replace(" ", "_"))
                if not os.path.exists(model_dir):
                    os.makedirs(model_dir)
                
                # Create a sanitized filename from the prompt
                sanitized_prompt = re.sub(r'[^\w\s-]', '', prompt)
                sanitized_prompt = re.sub(r'[\s-]+', '_', sanitized_prompt)
                sanitized_prompt = sanitized_prompt[:50]  # Limit length
                
                # Add timestamp to ensure uniqueness
                timestamp = int(time.time())
                filename = f"{sanitized_prompt}_{timestamp}.png"
                filepath = os.path.join(model_dir, filename)
                
                # Save image to file
                with open(filepath, 'wb') as f:
                    f.write(image_data)
                
                # Open image and add to carousel
                image = Image.open(io.BytesIO(image_data))
                self.root.after(0, lambda: self.add_to_carousel(image, model_name, filepath))
                
                self.root.after(0, lambda: self.add_log(f"Image generated by {model_name} and saved at {filepath}"))
            else:
                error_msg = f"Error downloading image from {model_name}: HTTP {response.status_code}"
                self.root.after(0, lambda: self.add_log(error_msg))
                
        except requests.exceptions.Timeout:
            error_msg = f"Timeout downloading image from {model_name}"
            self.root.after(0, lambda: self.add_log(error_msg))
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error with {model_name}: {str(e)}"
            self.root.after(0, lambda: self.add_log(error_msg))
        except concurrent.futures.TimeoutError:
            error_msg = f"Generation timeout for {model_name} after {self.generation_timeout} seconds"
            self.root.after(0, lambda: self.add_log(error_msg))
        except Exception as e:
            error_msg = f"Failed to generate image with {model_name}: {str(e)}"
            self.root.after(0, lambda: self.add_log(error_msg))
        finally:
            # Mark this generation as complete
            self.active_generations[model_name] = "completed"
            
            # If all generations are complete, signal the event
            if all(status in ["completed", "canceled"] for status in self.active_generations.values()):
                complete_event.set()
    
    def _check_generation_status(self, futures, complete_event):
        """Check the status of image generation threads and update UI accordingly"""
        # Count active generations
        active_count = sum(1 for status in self.active_generations.values() if status in ["queued", "running"])
        
        # Update progress
        completed_count = sum(1 for status in self.active_generations.values() if status == "completed")
        canceled_count = sum(1 for status in self.active_generations.values() if status == "canceled")
        total_count = len(self.active_generations)
        
        if active_count > 0:
            self.progress_var.set(f"Generating: {completed_count}/{total_count} completed, {canceled_count} canceled, {active_count} active")
            # Check again in 1 second
            self.root.after(1000, self._check_generation_status, futures, complete_event)
        elif complete_event.is_set() or all(f.done() for f in futures):
            # All tasks completed or were canceled
            self.progress_var.set(f"Generation complete: {completed_count}/{total_count} images generated, {canceled_count} canceled")
            self.re_enable_generate_button()
            
            # Show the carousel window if we have images
            if self.carousel_images:
                self.show_carousel()
        else:
            # Unusual state - maybe all threads ended but didn't signal completion
            self.progress_var.set("All generations completed or timed out")
            self.re_enable_generate_button()
            
            # Show the carousel window if we have images
            if self.carousel_images:
                self.show_carousel()
    
    def re_enable_generate_button(self):
        """Re-enable the generate button and disable the cancel button"""
        self.generate_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.DISABLED)
        self.add_log("Ready for next generation")
    
    def cancel_generation(self):
        """Cancel all active generations"""
        # Mark all ongoing generations as canceled
        for model_name, status in self.active_generations.items():
            if status in ["queued", "running"]:
                self.active_generations[model_name] = "canceled"
                self.add_log(f"Canceling generation for {model_name}")
        
        # Update UI
        self.progress_var.set("Canceling all active generations...")
        self.add_log("Canceled all active generations")
        
        # Re-enable the generate button
        self.re_enable_generate_button()
    
    def add_to_carousel(self, image, model_name, filepath):
        """Add an image to the carousel collection"""
        self.carousel_images.append((image, model_name, filepath))
        
        # Update existing carousel if it's open
        if self.carousel and self.carousel.winfo_exists():
            self.carousel.add_image(image, model_name, filepath)
    
    def show_carousel(self):
        """Show the image carousel in a new window"""
        # Check if carousel already exists and is open
        if self.carousel and self.carousel.winfo_exists():
            self.carousel.lift()  # Bring to front
            return
            
        # Create new carousel
        self.carousel = ImageCarousel(self.root, self.carousel_images)
        self.carousel.title(f"Generated Images - {len(self.carousel_images)} images")
    
    def on_closing(self):
        """Handle application closing - ensure clean shutdown"""
        try:
            # Close carousel if open
            if self.carousel and self.carousel.winfo_exists():
                self.carousel.destroy()
                
            # Shut down thread executor
            self.executor.shutdown(wait=False)
            self.root.destroy()
        except:
            # Force destroy if there's an error
            self.root.destroy()

class RoundedButton(tk.Canvas):
    """Custom canvas button with rounded corners"""
    def __init__(self, parent, width, height, corner_radius, bg_color, fg_color, text, command=None, **kwargs):
        super().__init__(parent, width=width, height=height, bg=kwargs.get('bg', parent['bg']), 
                         highlightthickness=0, relief='ridge', **kwargs)
        
        self.corner_radius = corner_radius
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.text = text
        self.command = command
        
        # Initial color states
        self.normal_bg = bg_color
        self.hover_bg = self._adjust_color(bg_color, 1.1)  # Slightly lighter
        self.pressed_bg = self._adjust_color(bg_color, 0.9)  # Slightly darker
        
        self._pressed = False
        self._drawing()
        
        # Event bindings
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        
    def _drawing(self):
        """Draw the button"""
        bg_color = self.pressed_bg if self._pressed else self.bg_color
        
        # Create rounded rectangle
        self.delete("all")
        self._create_rounded_rect(0, 0, self.winfo_width(), self.winfo_height(), 
                                 self.corner_radius, fill=bg_color, outline=bg_color)
        
        # Add text
        self.create_text(self.winfo_width()/2, self.winfo_height()/2, text=self.text, 
                         fill=self.fg_color, font=('Helvetica', 11, 'bold'))
    
    def _create_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        """Create a rounded rectangle"""
        points = [
            x1+radius, y1,
            x2-radius, y1,
            x2, y1,
            x2, y1+radius,
            x2, y2-radius,
            x2, y2,
            x2-radius, y2,
            x1+radius, y2,
            x1, y2,
            x1, y2-radius,
            x1, y1+radius,
            x1, y1]
        
        return self.create_polygon(points, **kwargs, smooth=True)
    
    def _on_press(self, event):
        """Handle button press event"""
        self._pressed = True
        self.bg_color = self.pressed_bg
        self._drawing()
        
    def _on_release(self, event):
        """Handle button release event"""
        self._pressed = False
        self.bg_color = self.hover_bg
        self._drawing()
        if self.command:
            self.command()
            
    def _on_enter(self, event):
        """Handle mouse enter event"""
        if not self._pressed:
            self.bg_color = self.hover_bg
            self._drawing()
            
    def _on_leave(self, event):
        """Handle mouse leave event"""
        if not self._pressed:
            self.bg_color = self.normal_bg
            self._drawing()
    
    def _adjust_color(self, hex_color, factor):
        """Adjust hex color brightness by a factor"""
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (1, 3, 5))
        rgb_adjusted = [min(255, max(0, int(c * factor))) for c in rgb]
        return f"#{rgb_adjusted[0]:02x}{rgb_adjusted[1]:02x}{rgb_adjusted[2]:02x}"
    
    def configure(self, **kwargs):
        """Override configure method to handle custom options"""
        if 'text' in kwargs:
            self.text = kwargs.pop('text')
        if 'bg_color' in kwargs:
            self.bg_color = kwargs.pop('bg_color')
            self.normal_bg = self.bg_color
            self.hover_bg = self._adjust_color(self.bg_color, 1.1)
            self.pressed_bg = self._adjust_color(self.bg_color, 0.9)
        if 'fg_color' in kwargs:
            self.fg_color = kwargs.pop('fg_color')
        if 'command' in kwargs:
            self.command = kwargs.pop('command')
        
        super().configure(**kwargs)
        self._drawing()
    
    def config(self, **kwargs):
        """Alias for configure"""
        self.configure(**kwargs)

class RoundedFrame(tk.Canvas):
    """Custom canvas frame with rounded corners"""
    def __init__(self, parent, width, height, corner_radius, bg_color, **kwargs):
        super().__init__(parent, width=width, height=height, bg=kwargs.get('bg', parent['bg']),
                         highlightthickness=0, **kwargs)
        
        self.corner_radius = corner_radius
        self.bg_color = bg_color
        
        # Create frame
        self.bind("<Configure>", self._on_resize)
        
    def _on_resize(self, event):
        """Handle resize event"""
        self._create_rounded_frame()
        
    def _create_rounded_frame(self):
        """Create the rounded frame"""
        self.delete("all")
        width, height = self.winfo_width(), self.winfo_height()
        
        # Create rounded rectangle
        self.create_rounded_rect(0, 0, width, height, self.corner_radius)
        
    def create_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        """Create a rounded rectangle"""
        kwargs.setdefault("fill", self.bg_color)
        kwargs.setdefault("outline", self.bg_color)
        
        points = [
            x1+radius, y1,
            x2-radius, y1,
            x2, y1,
            x2, y1+radius,
            x2, y2-radius,
            x2, y2,
            x2-radius, y2,
            x1+radius, y2,
            x1, y2,
            x1, y2-radius,
            x1, y1+radius,
            x1, y1]
        
        return self.create_polygon(points, **kwargs, smooth=True)
    
    def configure(self, **kwargs):
        """Override configure method to handle custom options"""
        if 'bg_color' in kwargs:
            self.bg_color = kwargs.pop('bg_color')
        
        super().configure(**kwargs)
        self._create_rounded_frame()
    
    def config(self, **kwargs):
        """Alias for configure"""
        self.configure(**kwargs)

class ImageCarousel(tk.Toplevel):
    """A window for displaying images in a carousel format"""
    def __init__(self, parent, images=None):
        super().__init__(parent)
        
        # Configure window
        self.title("Generated Images")
        self.geometry("800x600")
        self.minsize(600, 500)
        
        # Colors
        self.bg_color = "#f8f9fa"  # Off-white background
        self.accent_color = "#6c757d"  # Steel gray
        self.primary_color = "#4285f4"  # Modern blue
        
        # Image data format: [(image, model_name, filepath), ...]
        self.images = images or []
        self.current_index = 0
        
        # Set window background
        self.configure(bg=self.bg_color)
        
        self.create_widgets()
        self.update_display()
        
        # Set up key bindings
        self.bind("<Left>", lambda e: self.prev_image())
        self.bind("<Right>", lambda e: self.next_image())
        self.bind("<Escape>", lambda e: self.destroy())
        
        # Center window on screen
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        
    def create_widgets(self):
        """Create all the widgets for the carousel"""
        # Main frame
        self.main_frame = tk.Frame(self, bg=self.bg_color)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Image display area
        self.image_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.image_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.image_label = tk.Label(self.image_frame, bg=self.bg_color)
        self.image_label.pack(fill=tk.BOTH, expand=True)
        
        # Navigation area
        self.nav_frame = tk.Frame(self.main_frame, bg=self.bg_color, height=100)
        self.nav_frame.pack(fill=tk.X, pady=10)
        
        # Left button
        self.left_btn = RoundedButton(
            self.nav_frame, 
            width=60, 
            height=40, 
            corner_radius=20, 
            bg_color=self.accent_color, 
            fg_color="#ffffff", 
            text="←", 
            command=self.prev_image
        )
        self.left_btn.grid(row=0, column=0, padx=10)
        
        # Info area
        self.info_frame = tk.Frame(self.nav_frame, bg=self.bg_color)
        self.info_frame.grid(row=0, column=1, padx=10)
        
        # Model name
        self.model_label = tk.Label(
            self.info_frame, 
            text="", 
            font=("Helvetica", 12, "bold"), 
            bg=self.bg_color,
            fg=self.accent_color
        )
        self.model_label.pack(pady=5)
        
        # Image counter
        self.counter_label = tk.Label(
            self.info_frame, 
            text="", 
            font=("Helvetica", 10), 
            bg=self.bg_color,
            fg=self.accent_color
        )
        self.counter_label.pack()
        
        # Right button
        self.right_btn = RoundedButton(
            self.nav_frame, 
            width=60, 
            height=40, 
            corner_radius=20, 
            bg_color=self.accent_color, 
            fg_color="#ffffff", 
            text="→", 
            command=self.next_image
        )
        self.right_btn.grid(row=0, column=2, padx=10)
        
        # Configure grid layout
        self.nav_frame.grid_columnconfigure(1, weight=1)
        
    def update_display(self):
        """Update the display with the current image"""
        if not self.images:
            self.model_label.config(text="No images to display")
            self.counter_label.config(text="")
            return
        
        # Get current image data
        image, model_name, filepath = self.images[self.current_index]
        
        # Resize image to fit the display area while maintaining aspect ratio
        max_width = self.image_frame.winfo_width() - 40
        max_height = self.image_frame.winfo_height() - 40
        
        if max_width <= 0:  # Not yet properly sized
            max_width = 700
        if max_height <= 0:
            max_height = 400
            
        img_width, img_height = image.size
        scale = min(max_width/max(img_width, 1), max_height/max(img_height, 1))
        
        new_width = int(img_width * scale)
        new_height = int(img_height * scale)
        
        resized_image = image.resize((new_width, new_height), Image.LANCZOS)
        
        # Convert to PhotoImage
        tk_image = ImageTk.PhotoImage(resized_image)
        
        # Update image in label
        self.image_label.configure(image=tk_image)
        self.image_label.image = tk_image  # Keep a reference
        
        # Update labels
        self.model_label.config(text=f"Model: {model_name}")
        self.counter_label.config(text=f"Image {self.current_index + 1} of {len(self.images)}")
        
        # Update button states
        self.left_btn.config(state=tk.NORMAL if self.current_index > 0 else tk.DISABLED)
        self.right_btn.config(state=tk.NORMAL if self.current_index < len(self.images) - 1 else tk.DISABLED)
    
    def add_image(self, image, model_name, filepath):
        """Add a new image to the carousel"""
        self.images.append((image, model_name, filepath))
        if len(self.images) == 1:  # First image
            self.update_display()
    
    def next_image(self):
        """Show the next image"""
        if not self.images or self.current_index >= len(self.images) - 1:
            return
            
        self.current_index += 1
        self.update_display()
    
    def prev_image(self):
        """Show the previous image"""
        if not self.images or self.current_index <= 0:
            return
            
        self.current_index -= 1
        self.update_display()
    
    def reset(self):
        """Clear all images and reset the carousel"""
        self.images = []
        self.current_index = 0
        self.update_display()

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageGeneratorApp(root)
    # Set up proper app closing
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop() 