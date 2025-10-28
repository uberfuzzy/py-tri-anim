from math import cos, pi
import random
from PIL import Image, ImageDraw
import time


def lerp(a, b, t):
    """Linear interpolation between a and b for t in [0,1]."""
    return int(a + (b - a) * t)


def interp_color(color1, color2, t):
    """Interpolate between two RGB tuples."""
    return tuple(lerp(c1, c2, t) for c1, c2 in zip(color1, color2))


def make_fading_shape(path="shape.gif", size=(512, 512), frames_count=30, duration=120, seed=None, tile_size=8):
    """Create a GIF of a shape fading through the configured colors (looping).

    - path: output filename
    - size: (width, height)
    - frames_count: total frames in one loop
    - duration: ms per frame
    """
    # Color stops define the sequence the grid will fade through.
    # Each entry is an RGB tuple. You can change the number of stops and
    # brightness range below. This configuration generates 32 shades of
    # gray evenly stepped between 25% (0.25) and 80% (0.80) brightness.
    #
    # Brightness values are in [0,1] and are mapped to 0..255 for RGB.
    grey_count = 8
    min_bright = 0.10
    max_bright = 0.5

    def bright_to_rgb(b):
        v = int(round(255 * b))
        return (v, v, v)

    color_stops = [
        bright_to_rgb(min_bright + (max_bright - min_bright) * (i / (grey_count - 1)))
        for i in range(grey_count)
    ]

    # Convenience: length and helper to sample the multi-stop gradient
    stops_count = len(color_stops)

    frames = []
    w, h = size

    # Grid layout derived from desired square size (tile_size).
    # We'll compute column widths and row heights so the tiles exactly fill
    # the canvas and there are no gaps due to integer division.
    # tile_size = 8  # nominal pixels per square (used to choose cols/rows)
    padding = 0
    # horizontal pitch is half the tile so adjacent columns interlock
    tile_w = tile_size
    half = max(1, tile_w // 2)
    base_cols = max(1, (w + half - 1) // half)
    # Add one extra column to the left (off-screen) so left gaps are filled
    cols = base_cols + 1
    rows = max(1, h // tile_size)

    # For interlocking columns we use a fixed tile width and half-step pitch
    # for x positions. We clamp each tile to the canvas when drawing.
    col_widths = [tile_w] * cols
    # Start x positions shifted left by half so column 0 is off-screen
    col_x = [(i - 1) * half for i in range(cols)]

    base_h = h // rows
    extra_h = h % rows
    row_heights = [base_h + (1 if i < extra_h else 0) for i in range(rows)]
    row_y = []
    y_acc = 0
    for rh in row_heights:
        row_y.append(y_acc)
        y_acc += rh

    # Per-cell phase offsets so each square starts at a different color along
    # the same cycle. By default these are randomized; pass `seed` to make
    # the randomness reproducible.
    total_cells = cols * rows
    if seed is not None:
        random.seed(seed)
    cell_phase_offsets = [random.random() for _ in range(total_cells)]

    # We'll render RGBA frames with fully transparent background, then convert
    # to a paletted GIF while preserving transparency.
    def sample_multistop_color(u):
        """Sample the multi-stop color gradient at u in [0,1).

        We map u onto the sequence of segments between consecutive stops.
        For N stops there are N-1 segments; u * (N-1) selects segment and
        fractional position inside it. We use cosine easing for smooth
        transitions per segment.
        """
        if u >= 1.0:
            u = 0.0

        # Create a sinusoidal ping-pong along [0,1]: this makes the
        # progression go 0 -> 1 -> 0 smoothly as u goes 0 -> 1.
        # Using cosine gives a sine-like smoothness.
        ping = 0.5 * (1 - cos(2 * pi * u))  # 0..1..0

        # Map the ping value across the segments (N-1)
        seg_pos = ping * (stops_count - 1)
        seg_idx = int(seg_pos)
        if seg_idx >= stops_count - 1:
            seg_idx = stops_count - 2
        local_t = seg_pos - seg_idx

        # cosine ease for the local interpolation to make transitions smooth
        t_local = 0.5 * (1 - cos(pi * local_t))

        c1 = color_stops[seg_idx]
        c2 = color_stops[seg_idx + 1]
        return interp_color(c1, c2, t_local)

    # Generate exactly frames_count samples (0..frames_count-1). Because the
    # ping mapping used below is periodic with period 1, the color for
    # phase + 1 equals the color for phase, so the GIF will loop perfectly
    # (the next frame after the last is the same as the first) without a
    # duplicated final frame.
    for i in range(frames_count):
        # global phase in [0,1)
        phase = i / frames_count

        # Create RGBA image with transparent background
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw each cell with its own phase offset
        for idx in range(cols * rows):
            cell_col = idx % cols
            cell_row = idx // cols
            offset = cell_phase_offsets[idx % len(cell_phase_offsets)]
            cell_phase = (phase + offset) % 1.0
            col = sample_multistop_color(cell_phase)

            x0 = col_x[cell_col]
            y0 = row_y[cell_row]
            x1 = x0 + col_widths[cell_col]
            y1 = y0 + row_heights[cell_row]

            # Allow left-side drawing (x0 may be negative) and right-side
            # drawing (x1 may exceed width). Clamp only vertical bounds.
            y0 = max(0, y0)
            y1 = min(h, y1)

            # Overlap between tiles; set to 0 so triangles abut exactly.
            overlap = 0
            x0o = max(0, x0 - overlap)
            y0o = max(0, y0 - overlap)
            x1o = min(w, x1 + overlap)
            y1o = min(h, y1 + overlap)

            # Alternate triangle orientation for variety: if (row+col) is even
            # draw an upward-pointing triangle, otherwise downward.
            if ((cell_row + cell_col) % 2) == 0:
                # Up-pointing triangle: bottom-left, bottom-right, top-center
                points = [(x0o, y1o), (x1o, y1o), ((x0o + x1o) // 2, y0o)]
            else:
                # Down-pointing triangle: top-left, top-right, bottom-center
                points = [(x0o, y0o), (x1o, y0o), ((x0o + x1o) // 2, y1o)]

            draw.polygon(points, fill=col + (255,))

        # Convert to P mode (palette) which GIF uses. To preserve transparency
        # we create a paletted image with a dedicated transparent color index.
        # Approach: paste RGBA onto a transparent background and quantize.
        pal = img.convert("RGBA")
        # Create a white background image to ensure white appears in palette
        # when a shape is white; we'll later mark fully-transparent pixels as
        # transparent in the palette.
        background = Image.new("RGBA", size, (255, 255, 255, 0))
        composed = Image.alpha_composite(background, pal)

        # Quantize to 256 colors (required for GIF) using adaptive palette
        p = composed.convert("P", palette=Image.ADAPTIVE, colors=256)

        # Find a color index to use as transparent. We'll pick the color of a
        # fully transparent pixel in the RGBA image (which in composed will be
        # (255,255,255,0) -> after conversion it maps to some palette index).
        # To be robust, explicitly set any pixel that was transparent in the
        # RGBA source to a single palette index we reserve for transparency.
        alpha = img.split()[-1]
        mask = Image.eval(alpha, lambda a: 255 if a == 0 else 0)

        # Choose a transparency index (use the last palette entry)
        transp_index = 255

        # Build a palette image we can modify: get the palette bytes
        palette = p.getpalette()

        # Ensure palette length is 768 (256*3)
        if palette is None:
            palette = [0] * 768

        # Create an image where transparent areas are set to the transparency index
        p_bytes = p.tobytes()
        # Map pixels: where mask==255, set index to transp_index
        p2 = Image.frombytes("P", p.size, p_bytes)
        p2.paste(transp_index, mask=mask)

        # Ensure the palette is attached and set transparency
        p2.putpalette(p.getpalette())
        p2.info['transparency'] = transp_index

        frames.append(p2)

    # Save as looping GIF with transparency preserved
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        transparency=frames[0].info.get('transparency', 255),
        disposal=2,
    )


if __name__ == "__main__":
    # Use a fixed seed for reproducible random starting positions when run
    # directly. You can change or remove the seed for more variation.
    i_size = 512
    seed = int(time.time())

    t_sizes = [64,8]
    for t_size in t_sizes:
        fn = "shape_{}_{}.gif".format(i_size, t_size)
        make_fading_shape(path=fn, seed=seed, size=(i_size, i_size), tile_size=t_size)

