import os
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import replicate
from PIL import Image, ImageTk
import io
import requests

class ImageGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Image Generator")
        self.root.geometry("800x600")
        self.root.configure(bg="#f0f0f0")
        
        # Set application style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Configure colors
        self.primary_color = "#4285f4"  # Google blue
        self.bg_color = "#f0f0f0"
        self.accent_color = "#fbbc05"  # Google yellow
        
        self.style.configure('TFrame', background=self.bg_color)
        self.style.configure('TLabel', background=self.bg_color, font=('Helvetica', 10))
        self.style.configure('TEntry', font=('Helvetica', 10))
        self.style.configure('TButton', 
                             font=('Helvetica', 10, 'bold'),
                             background=self.primary_color,
                             foreground='white')
        
        # Available models dictionary with name and ID
        self.available_models = {
            "Flux Schnell": "black-forest-labs/flux-schnell",
            "Recraft-v": "recraft-ai/recraft-v3",
            "Stable Diffusion XL": "stability-ai/sdxl",
            "Midjourney v5": "lucataco/midjourney-v5"
        }
        
        self.create_widgets()
        
    def create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Title
        title_label = ttk.Label(main_frame, text="AI Image Generator", font=('Helvetica', 16, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # API Token frame
        token_frame = ttk.Frame(main_frame)
        token_frame.pack(fill=tk.X, pady=10)
        
        token_label = ttk.Label(token_frame, text="Replicate API Token:")
        token_label.pack(anchor=tk.W)
        
        self.token_entry = ttk.Entry(token_frame, width=50, show="•")
        self.token_entry.pack(fill=tk.X, pady=5)
        
        # Preset token from environment if available
        api_token = os.environ.get("REPLICATE_API_TOKEN", "")
        if api_token:
            self.token_entry.insert(0, api_token)
        
        # Prompt frame
        prompt_frame = ttk.Frame(main_frame)
        prompt_frame.pack(fill=tk.X, pady=10)
        
        prompt_label = ttk.Label(prompt_frame, text="Image Prompt:")
        prompt_label.pack(anchor=tk.W)
        
        self.prompt_text = tk.Text(prompt_frame, height=4, width=50, wrap=tk.WORD,
                                  font=('Helvetica', 10))
        self.prompt_text.pack(fill=tk.X, pady=5)
        self.prompt_text.insert(tk.END, "an iguana on the beach, pointillism")
        
        # Model selection frame
        model_frame = ttk.Frame(main_frame)
        model_frame.pack(fill=tk.X, pady=10)
        
        model_label = ttk.Label(model_frame, text="AI Model:")
        model_label.pack(anchor=tk.W)
        
        # Create dropdown for model selection
        self.model_var = tk.StringVar()
        self.model_dropdown = ttk.Combobox(model_frame, textvariable=self.model_var, state="readonly")
        self.model_dropdown['values'] = list(self.available_models.keys())
        self.model_dropdown.current(0)  # Set default to first item
        self.model_dropdown.pack(fill=tk.X, pady=5)
        
        # Advanced options frame (collapsible)
        self.advanced_frame = ttk.Frame(main_frame)
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
        self.advanced_options = ttk.Frame(main_frame)
        
        # Custom model ID entry
        custom_model_frame = ttk.Frame(self.advanced_options)
        custom_model_frame.pack(fill=tk.X, pady=5)
        
        custom_model_label = ttk.Label(custom_model_frame, text="Custom Model ID:")
        custom_model_label.pack(anchor=tk.W)
        
        self.custom_model_entry = ttk.Entry(custom_model_frame, width=50)
        self.custom_model_entry.pack(fill=tk.X, pady=5)
        
        # Generate button
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        self.generate_button = tk.Button(
            button_frame, 
            text="Generate Image",
            bg=self.primary_color,
            fg="white",
            font=('Helvetica', 11, 'bold'),
            relief=tk.FLAT,
            padx=15,
            pady=8,
            command=self.generate_image
        )
        self.generate_button.pack(pady=10)
        
        # Progress indicator
        self.progress_var = tk.StringVar(value="")
        self.progress_label = ttk.Label(button_frame, textvariable=self.progress_var)
        self.progress_label.pack(pady=5)
        
        # Image display frame
        self.image_frame = ttk.Frame(main_frame)
        self.image_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.image_label = ttk.Label(self.image_frame)
        self.image_label.pack(fill=tk.BOTH, expand=True)
    
    def toggle_advanced_options(self):
        if self.show_advanced.get():
            self.advanced_options.pack(fill=tk.X, pady=5, after=self.advanced_frame)
        else:
            self.advanced_options.pack_forget()
    
    def get_selected_model(self):
        # Get the selected model ID (either from dropdown or custom entry)
        if self.show_advanced.get() and self.custom_model_entry.get().strip():
            return self.custom_model_entry.get().strip()
        else:
            selected_name = self.model_var.get()
            return self.available_models[selected_name]
    
    def generate_image(self):
        # Get API token and prompt
        api_token = self.token_entry.get().strip()
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        model = self.get_selected_model()
        
        if not api_token:
            messagebox.showerror("Error", "Please enter your Replicate API token")
            return
        
        if not prompt:
            messagebox.showerror("Error", "Please enter an image prompt")
            return
        
        # Disable button and show progress
        self.generate_button.config(state=tk.DISABLED)
        self.progress_var.set("Generating image with " + model + "... Please wait")
        
        # Run generation in a separate thread to keep UI responsive
        threading.Thread(target=self._generate_image_thread, 
                        args=(api_token, prompt, model), 
                        daemon=True).start()
    
    def _generate_image_thread(self, api_token, prompt, model):
        try:
            # Set API token
            os.environ["REPLICATE_API_TOKEN"] = api_token
            
            # Run model
            output = replicate.run(
                model,
                input={"prompt": prompt}
            )
            
            # Download and display image
            # Different models may return results in different formats
            image_url = output[0] if isinstance(output, list) else output
            
            response = requests.get(image_url)
            if response.status_code == 200:
                image_data = response.content
                
                # Save image to file
                filename = f"output_{model.replace('/', '_')}.png"
                with open(filename, 'wb') as f:
                    f.write(image_data)
                
                # Display image in UI
                image = Image.open(io.BytesIO(image_data))
                self.display_image(image)
                
                self.progress_var.set(f"Image generated and saved as {filename}")
            else:
                self.progress_var.set("Error downloading image")
                messagebox.showerror("Error", "Failed to download generated image")
                
        except Exception as e:
            self.progress_var.set("Error generating image")
            messagebox.showerror("Error", f"Failed to generate image: {str(e)}")
        finally:
            # Re-enable button
            self.root.after(0, lambda: self.generate_button.config(state=tk.NORMAL))
    
    def display_image(self, pil_image):
        # Resize image to fit in the frame while maintaining aspect ratio
        max_width = self.image_frame.winfo_width() - 20
        max_height = 300
        
        img_width, img_height = pil_image.size
        scale = min(max_width/img_width, max_height/img_height)
        
        new_width = int(img_width * scale)
        new_height = int(img_height * scale)
        
        resized_image = pil_image.resize((new_width, new_height), Image.LANCZOS)
        
        # Convert to PhotoImage and display
        tk_image = ImageTk.PhotoImage(resized_image)
        
        # Keep a reference to prevent garbage collection
        self.tk_image = tk_image
        
        # Update image in label
        self.image_label.configure(image=tk_image)
        self.image_label.image = tk_image

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageGeneratorApp(root)
    root.mainloop() 