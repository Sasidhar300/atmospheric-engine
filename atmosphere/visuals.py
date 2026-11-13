"""Periodic masked compositing and original illustrative fallback artwork."""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def illustration(size=(1920, 1080), seed=431):
    w, h = size
    rng = np.random.default_rng(seed)
    y, x = np.ogrid[:h, :w]
    glow = np.exp(-((x / w - .17) ** 2 + (y / h - .61) ** 2) * 22)
    grain = rng.normal(0, .65, (h, w))
    room = np.stack([14 + 54*glow + grain, 18 + 25*glow + grain, 29 + 7*glow + grain], axis=-1)
    image = Image.fromarray(room.clip(0, 255).astype("uint8"))
    draw = ImageDraw.Draw(image)

    def box(coords, color, radius=0):
        a, b, c, d = coords
        bounds = (round(a*w), round(b*h), round(c*w), round(d*h))
        draw.rounded_rectangle(bounds, radius=int(radius*h), fill=color)

    def poly(coords, color):
        draw.polygon([(int(a*w), int(b*h)) for a, b in coords], fill=color)

    box((.289,.099,.946,.697), "#101321", .012)
    for row in range(int(.12*h), int(.673*h)+1):
        k = row/h
        draw.line((int(.303*w), row, int(.932*w), row), fill=(int(18+24*k), int(28+42*k), int(53+49*k)))
    for depth in range(3):
        left = .304
        base = .57 + depth*.056
        while left < .925:
            width = min(rng.uniform(.022, .075), .931-left)
            top = base-rng.uniform(.08,.29)*(1+depth*.13)
            right = left+width
            box((left, top, right, base), [(37,52,75),(28,40,62),(19,28,48)][depth])
            box((left+.003, top-.012, max(left+.003,right-.003), top), (31+depth*3,43,65))
            for yy in np.arange(top+.017, base-.006, .014):
                for xx in np.arange(left+.005, right-.004, .009):
                    if rng.random() < .35:
                        color = [(56,108,139),(141,75,116),(182,136,101),(69,135,142)][rng.integers(4)]
                        box((xx, yy, xx+.0035, yy+.0023), color)
            if width > .048 and rng.random() > .48:
                box((left+.008,top+.007,right-.008,top+.010), "#a25086")
            left = right+rng.uniform(.004,.012)
    city = image.crop((int(.303*w), int(.12*h), int(.932*w), int(.673*h)))
    image.paste(Image.blend(city, city.filter(ImageFilter.GaussianBlur(w*.002)), .34),
                (int(.303*w), int(.12*h)))
    for edge in (.506, .718):
        box((edge,.119,edge+.008,.675), "#171722")
        box((edge+.001,.12,edge+.002,.673), "#373345")
    box((.296,.672,.940,.683), "#3f3944")
    poly([(0,.88),(.303,.694),(.94,.694),(1,.87),(1,1),(0,1)], "#221d27")
    for xx in np.arange(-1,2,.17):
        draw.line((int((.62+.13*(xx-.62))*w),int(.70*h),int(xx*w),h), fill="#322a36", width=2)
    box((.05,.225,.232,.485), "#211b27", .009)
    box((.058,.236,.224,.472), "#2d2330", .005)
    for j in range(11):
        yy = .263 + j*.014
        poly([(.075,yy),(.205,yy-.027),(.195,yy-.023),(.078,yy+.006)], (52+j*2,38+j,48+j))
    box((.181,.58,.186,.82), "#765445")
    box((.152,.805,.211,.822), "#33262d", .004)
    poly([(.158,.512),(.205,.512),(.222,.594),(.141,.594)], "#a46b4d")
    box((.143,.588,.220,.596), "#e8aa6b")
    box((.282,.716,.650,.903), "#151520", .042)
    box((.296,.672,.636,.831), "#493846", .035)
    box((.310,.753,.626,.861), "#584451", .025)
    box((.284,.752,.331,.884), "#463644", .023)
    box((.612,.751,.662,.884), "#463644", .023)
    box((.345,.700,.424,.790), "#7d5354", .023)
    box((.443,.711,.515,.788), "#5e4b63", .023)
    box((.68,.879,.875,.91), "#392b36", .013)
    box((.701,.908,.708,.975), "#231d28")
    box((.845,.906,.852,.975), "#231d28")
    box((.749,.845,.775,.880), "#8d6458", .005)
    box((.779,.872,.829,.882), "#554258", .002)
    box((.863,.752,.911,.830), "#423440", .009)
    for end in [(.835,.66),(.864,.614),(.914,.63),(.935,.69),(.9,.61),(.88,.635)]:
        draw.line((int(.886*w),int(.764*h),int(end[0]*w),int(end[1]*h)), fill="#4c5d57", width=max(1,w//550))
    return image


def load_image(path: Path, size, alpha=False):
    with Image.open(path) as image:
        if abs(image.width / image.height - size[0] / size[1]) > .02:
            raise ValueError(f"Image aspect ratio does not match the scene: {path.name}")
        return np.asarray(image.convert("RGBA" if alpha else "RGB").resize(size, Image.Resampling.LANCZOS))


class Compositor:
    def __init__(self, scene, artwork, layers=(), mask=None):
        self.scene = scene
        w, h = scene.width, scene.height
        self.base = load_image(artwork, (w, h))
        self.layers = [(load_image(path, (w, h), True), depth) for path, depth in layers]
        self.mask = np.zeros((h, w), dtype=np.uint8)
        for name, value in (("windows", 255), ("occlusion", 0)):
            if name == "occlusion" and mask:
                with Image.open(mask) as image:
                    self.mask = np.array(image.convert("L").resize((w, h), Image.Resampling.BILINEAR))
            for polygon in scene.data.get(name, []):
                cv2.fillPoly(self.mask, [np.rint(np.asarray(polygon)*[w-1,h-1]).astype(np.int32)], value)
        rng = np.random.default_rng(scene.seed)
        self.drops = rng.random((320, 5))
        self.effects = scene.data.get("effects", {})
        active_rows = np.flatnonzero(np.any(self.mask, axis=1))
        self.y0, self.y1 = (int(active_rows[0]), int(active_rows[-1])+1) if active_rows.size else (0,1)
        ys, xs = np.ogrid[self.y0:self.y1, :w]
        self.haze = np.exp(-((xs/w-.71)**2*12 + (ys/h-.44)**2*29)).astype(np.float32)
        self.glow = np.exp(-((xs/w-.59)**2*38 + (ys/h-.45)**2*49)).astype(np.float32)
        self.glass = np.ascontiguousarray(self.mask[self.y0:self.y1])
        self.glass_alpha = self.glass.astype(np.float32)/255

    def render(self, index):
        w, h = self.scene.width, self.scene.height
        phase = (index % self.scene.frames) / self.scene.frames
        angle = np.pi * 2 * phase
        camera = self.scene.data.get("camera_pixels", 0)
        dx, dy = camera*np.sin(angle), camera*.55*(np.cos(angle)-1)
        frame = self.base.copy()
        rain = np.zeros(self.glass.shape, np.uint8)
        for x, y, speed, length, value in self.drops:
            cycles = max(1, round((.25 + speed*.41)*self.scene.duration))
            position = y + cycles * phase
            yy = int((position % 1) * h) - self.y0
            xx = int(w * ((x - .038*(position % 1)) % 1))
            tail = max(2, int((.006 + length*.02)*h))
            cv2.line(rain, (xx, yy), (xx+max(1,tail//5), yy-tail), int(35+115*value), 1, cv2.LINE_AA)
        intensity = self.effects.get("rain", .45)
        rain = cv2.multiply(rain, self.glass, scale=intensity/255)
        haze = self.haze*(9+3*np.sin(2*angle))*self.effects.get("haze", .1)
        glow = self.glow*(3+2*np.sin(7*angle)+np.cos(19*angle))*self.effects.get("flicker", .12)
        change = np.uint8((haze+glow)*self.glass_alpha)
        glass = frame[self.y0:self.y1]
        reflections = cv2.multiply(cv2.GaussianBlur(rain, (0, 0), 2.2), self.glass, scale=1/255)
        for channel, scale in enumerate((.55,.78,1)):
            addition = cv2.addWeighted(rain, scale, reflections, self.effects.get("reflections", .35), 0)
            glass[:,:,channel] = cv2.add(glass[:,:,channel], cv2.add(addition, change))
        if camera:
            frame = self.shift(frame, dx, dy)
        for layer, depth in self.layers:
            layer_frame = self.shift(layer, dx*depth, dy*depth) if camera else layer
            alpha = layer_frame[:,:,3:4].astype(np.float32)/255
            frame = np.uint8(frame*(1-alpha)+layer_frame[:,:,:3]*alpha+.5)
        return frame

    @staticmethod
    def shift(image, x, y):
        return cv2.warpAffine(image, np.float32([[1,0,x],[0,1,y]]), image.shape[1::-1],
                              flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
