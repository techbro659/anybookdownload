import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer, CircleModuleDrawer, SquareModuleDrawer
from qrcode.image.styles.colormasks import SquareGradiantColorMask
import os
from PIL import Image


class QRGenerator:
    """Generate QR codes with customization options"""
    
    def __init__(self, version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, 
                 box_size=10, border=4):
        """
        Initialize QR Generator
        
        Args:
            version: Version of QR code (1-40, higher = larger)
            error_correction: Error correction level (L, M, Q, H)
            box_size: Size of each box in pixels
            border: Border size in boxes
        """
        self.version = version
        self.error_correction = error_correction
        self.box_size = box_size
        self.border = border
    
    def generate_basic(self, data, file_path="qr_code.png", fill_color="black", back_color="white"):
        """
        Generate a basic QR code
        
        Args:
            data: Data to encode in QR code
            file_path: Output file path
            fill_color: Color of the QR pattern
            back_color: Background color
        
        Returns:
            file_path: Path to generated QR code
        """
        qr = qrcode.QRCode(
            version=self.version,
            error_correction=self.error_correction,
            box_size=self.box_size,
            border=self.border,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color=fill_color, back_color=back_color)
        img.save(file_path)
        print(f"QR code saved to {file_path}")
        return file_path
    
    def generate_styled(self, data, file_path="qr_code_styled.png", 
                       module_drawer="rounded", embed_image=None):
        """
        Generate a styled QR code with custom module drawer
        
        Args:
            data: Data to encode in QR code
            file_path: Output file path
            module_drawer: Style - "rounded", "circle", or "square"
            embed_image: Path to image to embed in QR code center (optional)
        
        Returns:
            file_path: Path to generated QR code
        """
        qr = qrcode.QRCode(
            version=self.version,
            error_correction=qrcode.constants.ERROR_CORRECT_H,  # Use high error correction
            box_size=self.box_size,
            border=self.border,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        # Select module drawer style
        drawer_map = {
            "rounded": RoundedModuleDrawer(),
            "circle": CircleModuleDrawer(),
            "square": SquareModuleDrawer(),
        }
        drawer = drawer_map.get(module_drawer, RoundedModuleDrawer())
        
        # Create styled image
        img = qr.make_image(
            image_factory=StyledPilImage,
            module_drawer=drawer,
        )
        
        # Embed image if provided
        if embed_image and os.path.exists(embed_image):
            self._embed_image(img, embed_image)
        
        img.save(file_path)
        print(f"Styled QR code saved to {file_path}")
        return file_path
    
    def _embed_image(self, qr_img, embed_image_path, size_ratio=0.3):
        """
        Embed an image in the center of QR code
        
        Args:
            qr_img: PIL Image of QR code
            embed_image_path: Path to image to embed
            size_ratio: Ratio of embedded image size to QR code (0-0.4 recommended)
        """
        try:
            embed_img = Image.open(embed_image_path).convert("RGBA")
            
            # Calculate size
            qr_width, qr_height = qr_img.size
            embed_size = int(min(qr_width, qr_height) * size_ratio)
            embed_img = embed_img.resize((embed_size, embed_size), Image.Resampling.LANCZOS)
            
            # Create white background for embedded image
            bg = Image.new("RGB", (embed_size + 10, embed_size + 10), "white")
            bg.paste(embed_img, (5, 5), embed_img)
            
            # Paste centered
            offset = ((qr_width - embed_size - 10) // 2, (qr_height - embed_size - 10) // 2)
            qr_img.paste(bg, offset)
            
        except Exception as e:
            print(f"Could not embed image: {e}")
    
    def generate_batch(self, data_list, output_dir="qr_codes"):
        """
        Generate multiple QR codes
        
        Args:
            data_list: List of data strings to encode
            output_dir: Directory to save QR codes
        
        Returns:
            List of file paths
        """
        os.makedirs(output_dir, exist_ok=True)
        file_paths = []
        
        for i, data in enumerate(data_list):
            file_path = os.path.join(output_dir, f"qr_code_{i+1}.png")
            self.generate_basic(data, file_path)
            file_paths.append(file_path)
        
        return file_paths


# Example usage
if __name__ == "__main__":
    # Create QR generator instance
    generator = QRGenerator(box_size=10, border=4)
    
    # Example 1: Basic QR code
    generator.generate_basic(
        "https://github.com/techbro659",
        "qr_code_basic.png"
    )
    
    # Example 2: Styled QR code with rounded modules
    generator.generate_styled(
        "https://github.com/techbro659/anybookdownload",
        "qr_code_styled_rounded.png",
        module_drawer="rounded"
    )
    
    # Example 3: Generate batch QR codes
    data_list = [
        "https://github.com/techbro659",
        "Hello World",
        "Contact: techbro659@example.com"
    ]
    generator.generate_batch(data_list, "output/qr_codes")
    
    print("\nQR code generation complete!")
