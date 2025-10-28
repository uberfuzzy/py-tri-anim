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
    # print(col_x)

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

    # For each row, make the last column's phase offset equal to the first's.
    # This ensures the off-screen left column (col 0) matches the rightmost
    # visible column so the pattern wraps horizontally.
    for r in range(rows):
        first_idx = r * cols
        last_idx = first_idx + cols - 1
        if last_idx < len(cell_phase_offsets):
            cell_phase_offsets[last_idx] = cell_phase_offsets[first_idx]

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

            x_left = col_x[cell_col]
            y_left = row_y[cell_row]
            x_right = x_left + col_widths[cell_col]
            y_right = y_left

            x_point = x_left + (col_widths[cell_col] // 2)
            y_point = y_left

            rh = row_heights[cell_row]

            # Alternate triangle orientation for variety: if (row+col) is even
            # draw an upward-pointing triangle, otherwise downward.
            if ((cell_row + cell_col) % 2) == 0:
                # Up-pointing triangle: bottom-left, bottom-right, top-center
                points = [(x_left, y_left+rh), (x_right, y_right+rh), (x_point, y_point)]
                # print("up:", points)
                draw.polygon(points, fill=col + (255,))
            else:
                # Down-pointing triangle: top-left, top-right, bottom-center
                points = [(x_left, y_left), (x_right, y_right), (x_point, y_point+rh)]
                # print("down:", points)
                draw.polygon(points, fill=col + (255,))
                pass



        # We no longer need to preserve transparency. Composite the RGBA frame
        # over a black opaque background and quantize to a 256-color palette
        # suitable for GIFs. This avoids special-case transparent palette indices
        # and simplifies saving.
        background = Image.new("RGBA", size, (0, 0, 0, 255))
        composed = Image.alpha_composite(background, img)

        # Quantize to 256 colors (required for GIF) using adaptive palette
        p = composed.convert("P", palette=Image.ADAPTIVE, colors=256)

        frames.append(p)

    # Save as looping GIF (opaque frames; no transparency)
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        optimize=False,
    )


if __name__ == "__main__":
    # Use a fixed seed for reproducible random starting positions when run
    # directly. You can change or remove the seed for more variation.
    i_size = 512
    seed = int(time.time())

    t_sizes = [8, 16, 64, 128]
    for t_size in t_sizes:
        fn = "shape_{}_{}.gif".format(i_size, t_size)
        print("creating file:{}".format(fn))
        make_fading_shape(path=fn, seed=seed, size=(i_size, i_size), tile_size=t_size)

