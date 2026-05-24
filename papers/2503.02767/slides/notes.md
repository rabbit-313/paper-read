# Notes

- Source paper: arXiv:2503.02767, "Undertrained Image Reconstruction for Realistic Degradation in Blind Image Super-Resolution".
- Source materials used: translated Markdown at `../2503.02767-ja-md/paper.ja.md`, extracted/source figure PNGs under `../2503.02767-ja-md/figures/`.
- Slide format: Ochiai paper-reading structure with white/blue HTML theme.
- Main quantitative values were taken from the translated Markdown generated from the arXiv TeX source:
  - HAT w/o fine-tune: PSNR 18.24, SSIM 0.4337, LPIPS 0.6272.
  - HAT + VQ-VAE-2 Ep 8: PSNR 18.10, SSIM 0.5288, LPIPS 0.5977.
  - EDSR Ep 8: SSIM +0.0871, LPIPS -0.0138.
  - ESRGAN Ep 8: SSIM +0.1266, LPIPS -0.0816.
  - SwinIR Ep 8: SSIM +0.0503.
- Caveat: PSNR does not consistently improve; the deck frames the result as improved perceptual/structural quality rather than uniform metric dominance.
