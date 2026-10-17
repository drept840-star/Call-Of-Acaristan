import sys, os, io, base64
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
pygame.init()
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outfit")
names = sys.argv[1].split(",")
cols = int(sys.argv[2]) if len(sys.argv) > 2 else 2
w = int(sys.argv[3]) if len(sys.argv) > 3 else 640
imgs = [pygame.image.load(os.path.join(D, n + ".png")) for n in names]
imgs = [pygame.transform.smoothscale(i, (w, int(i.get_height() * w / i.get_width()))) for i in imgs]
h = max(i.get_height() for i in imgs)
rows = (len(imgs) + cols - 1) // cols
sheet = pygame.Surface((cols * w, rows * h))
for k, i in enumerate(imgs):
    sheet.blit(i, ((k % cols) * w, (k // cols) * h))
out = os.path.join(D, "_sheet.jpg")
pygame.image.save(sheet, out)
print(base64.b64encode(open(out, "rb").read()).decode())
