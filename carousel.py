import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw


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

        self.normal_bg = bg_color
        self.hover_bg = self._adjust_color(bg_color, 1.1)
        self.pressed_bg = self._adjust_color(bg_color, 0.9)
        self.border_color = "#000000"

        self._pressed = False
        self._drawing()

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _drawing(self):
        """Draw the button"""
        bg_color = self.pressed_bg if self._pressed else self.bg_color

        self.delete("all")
        self._create_rounded_rect(0, 0, self.winfo_width(), self.winfo_height(),
                                  self.corner_radius, fill=bg_color, outline=self.border_color, width=2)

        self.create_text(self.winfo_width() / 2, self.winfo_height() / 2, text=self.text,
                         fill=self.fg_color, font=('Helvetica', 12, 'bold'))

    def _create_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        """Create a rounded rectangle"""
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
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
        rgb = tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
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


class ImageCarousel(tk.Toplevel):
    """A window for displaying images in a carousel format"""

    def __init__(self, parent, images=None):
        super().__init__(parent)

        # Check if parent is in arena mode
        self.arena_mode = hasattr(parent, 'arena_mode') and parent.arena_mode
        
        # Set window title based on mode
        if self.arena_mode:
            self.title("🏆 ARENA MODE - Image Battle 🏆")
        else:
            self.title("Generated Images")
            
        self.geometry("800x600")
        self.minsize(600, 500)

        if isinstance(parent, tk.Tk) or isinstance(parent, tk.Toplevel):
            if self.arena_mode:
                self.bg_color = "#000000"  # Black background for Arena Mode
                self.primary_color = "#00FF00"  # Neon green for Arena Mode
                self.accent_color = "#FF00FF"  # Magenta accent for Arena Mode
                self.button_text_color = "#000000"  # Black text on buttons
            else:
                self.bg_color = parent.cget("bg")
                if hasattr(parent, 'primary_color'):
                    self.primary_color = parent.primary_color
                    self.accent_color = parent.accent_color
                    self.button_text_color = parent.button_text_color
                else:
                    self.primary_color = "#FF9933"
                    self.accent_color = "#FF8C00"
                    self.button_text_color = "#000000"
        else:
            if self.arena_mode:
                self.bg_color = "#000000"  # Black background for Arena Mode
                self.primary_color = "#00FF00"  # Neon green for Arena Mode
                self.accent_color = "#FF00FF"  # Magenta accent for Arena Mode
                self.button_text_color = "#000000"  # Black text on buttons
            else:
                self.bg_color = "#f0f0f0"
                self.primary_color = "#FF9933"
                self.accent_color = "#FF8C00"
                self.button_text_color = "#000000"

        self.images = images or []
        self.current_index = 0

        self.configure(bg=self.bg_color)

        self.create_widgets()
        self.update_display()

        self.bind("<Left>", lambda e: self.prev_image())
        self.bind("<Right>", lambda e: self.next_image())
        self.bind("<Escape>", lambda e: self.destroy())

        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def create_widgets(self):
        """Create all the widgets for the carousel"""
        self.main_frame = tk.Frame(self, bg=self.bg_color)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Add header for Arena Mode
        if self.arena_mode:
            header_frame = tk.Frame(self.main_frame, bg="#000000", bd=5, relief="raised")
            header_frame.pack(fill=tk.X, pady=(0, 20))
            
            header_label = tk.Label(
                header_frame, 
                text="★ IMAGE BATTLE ARENA ★",
                bg="#000000", 
                fg="#00FF00",
                font=("Courier", 18, "bold")
            )
            header_label.pack(pady=10)

        self.image_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.image_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # For Arena Mode, create a special frame with arcade styling
        if self.arena_mode:
            image_bg_frame = tk.Frame(
                self.image_frame, 
                bg="#111111",
                bd=10,
                relief="ridge",
                highlightbackground="#00FF00",
                highlightthickness=3
            )
        else:
            image_bg_frame = tk.Frame(self.image_frame, bg=self.bg_color)
            
        image_bg_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.image_label = tk.Label(image_bg_frame, bg=self.bg_color)

        self.nav_frame = tk.Frame(self.main_frame, bg=self.bg_color, height=100)
        self.nav_frame.pack(fill=tk.X, pady=10)

        # Custom styling for buttons based on mode
        if self.arena_mode:
            self.left_btn = tk.Button(
                self.nav_frame,
                text="◄",
                bg=self.primary_color,
                fg=self.button_text_color,
                font=('Courier', 18, 'bold'),
                relief="raised",
                bd=4,
                width=3,
                height=1,
                command=self.prev_image
            )
        else:
            self.left_btn = RoundedButton(
                self.nav_frame,
                width=60,
                height=40,
                corner_radius=20,
                bg_color=self.primary_color,
                fg_color=self.button_text_color,
                text="←",
                command=self.prev_image
            )
            
        self.left_btn.grid(row=0, column=0, padx=10)

        self.info_frame = tk.Frame(self.nav_frame, bg=self.bg_color)
        self.info_frame.grid(row=0, column=1, padx=10)

        # Style model label based on mode
        if self.arena_mode:
            self.model_label = tk.Label(
                self.info_frame,
                text="",
                font=("Courier", 14, "bold"),
                bg=self.bg_color,
                fg="#00FF00"
            )
        else:
            self.model_label = tk.Label(
                self.info_frame,
                text="",
                font=("Helvetica", 12, "bold"),
                bg=self.bg_color,
                fg=self.accent_color
            )
            
        self.model_label.pack(pady=5)

        # Style counter label based on mode
        if self.arena_mode:
            self.counter_label = tk.Label(
                self.info_frame,
                text="",
                font=("Courier", 12),
                bg=self.bg_color,
                fg="#00FFFF"
            )
        else:
            self.counter_label = tk.Label(
                self.info_frame,
                text="",
                font=("Helvetica", 10),
                bg=self.bg_color,
                fg=self.accent_color
            )
            
        self.counter_label.pack()

        # Custom styling for right button based on mode
        if self.arena_mode:
            self.right_btn = tk.Button(
                self.nav_frame,
                text="►",
                bg=self.primary_color,
                fg=self.button_text_color,
                font=('Courier', 18, 'bold'),
                relief="raised",
                bd=4,
                width=3,
                height=1,
                command=self.next_image
            )
        else:
            self.right_btn = RoundedButton(
                self.nav_frame,
                width=60,
                height=40,
                corner_radius=20,
                bg_color=self.primary_color,
                fg_color=self.button_text_color,
                text="→",
                command=self.next_image
            )
            
        self.right_btn.grid(row=0, column=2, padx=10)

        self.nav_frame.grid_columnconfigure(1, weight=1)
        
        # Add battle instructions for Arena Mode
        if self.arena_mode:
            instructions_frame = tk.Frame(self.main_frame, bg="#000000", bd=3, relief="ridge")
            instructions_frame.pack(fill=tk.X, pady=(20, 0))
            
            instructions_text = """
            → VIEW ALL CONTENDERS WITH ARROW KEYS
            → PRESS ESC TO RETURN AND CAST YOUR VOTE
            """
            
            instructions_label = tk.Label(
                instructions_frame,
                text=instructions_text,
                font=("Courier", 10),
                bg="#000000",
                fg="#00FF00",
                justify=tk.LEFT
            )
            instructions_label.pack(padx=10, pady=10)

    def update_display(self):
        """Update the display with the current image"""
        if not self.images:
            self.model_label.config(text="No images to display")
            self.counter_label.config(text="")
            return

        image, model_name, filepath = self.images[self.current_index]

        max_width = self.image_frame.winfo_width() - 40
        max_height = self.image_frame.winfo_height() - 40

        if max_width <= 0:
            max_width = 700
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
            border_size = 15
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

        self.image_label.configure(image=tk_image)
        self.image_label.image = tk_image

        self.image_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Update text based on arena mode
        if self.arena_mode:
            self.model_label.config(text=f"CONTENDER #{self.current_index + 1}")
        else:
            self.model_label.config(text=f"Model: {model_name}")
            
        self.counter_label.config(text=f"Image {self.current_index + 1} of {len(self.images)}")

        self.left_btn.config(state=tk.NORMAL if self.current_index > 0 else tk.DISABLED)
        self.right_btn.config(state=tk.NORMAL if self.current_index < len(self.images) - 1 else tk.DISABLED)

    def add_image(self, image, model_name, filepath):
        """Add a new image to the carousel"""
        self.images.append((image, model_name, filepath))
        if len(self.images) == 1:
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

    def replace_image(self, index, image, model_name, filepath):
        """Replace an image at the specified index"""
        if 0 <= index < len(self.images):
            self.images[index] = (image, model_name, filepath)
            if self.current_index == index:
                self.update_display()