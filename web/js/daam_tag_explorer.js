import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { load } from "./lib/npyjs.js";

// Colour tiers relative to the even split: with N tags an indifferent cell
// gives every tag 1/N, so "high" means at least double that and "mid" means
// above average. Fixed cutoffs would shift meaning with the prompt length.
const SCORE_HIGH_RATIO = 2.0;
const SCORE_MID_RATIO = 1.0;
const SCORE_HIGH_COLOR = "#6ab0ff";
const SCORE_MID_COLOR = "#e8c14a";
const SCORE_LOW_COLOR = "#8a8a8a";

// The node scores each tag 0..1 against fixed floors, not against the other
// tags, so these cuts mean the same thing in every render: a prompt where
// nothing goes blue really did build nothing. Roughly a third blue and a
// fifth grey on the renders the floors were calibrated on, but nothing
// forces that -- which is the difference from ranking tags against
// each other.
const LANDED_CLEAR = 0.5;
const LANDED_AT_ALL = 0;

// A jet colour map blended over the image at a constant alpha: no opacity
// ramp, no grey base, so the picture stays visible underneath while the
// colour alone carries the magnitude.
const OVERLAY_ALPHA = 0.5;

// Mask mode dims instead of colouring, and a dimming worth looking at goes all
// the way down, so it starts at full strength. The slider carries one value per
// view and swaps them on toggle: half a jet overlay and a fully dark mask are
// both "the default look", and neither is a good default for the other.
const MASK_ALPHA = 1.0;

// selectedMap() min-max normalises, so the overlay always spans exactly this
// range and the colour bar can label its ends with fixed numbers.
const OVERLAY_MIN = 0;
const OVERLAY_MAX = 1;

function tierColor(share, tagCount) {
    const uniform = 1 / Math.max(1, tagCount);
    if (share > SCORE_HIGH_RATIO * uniform) return SCORE_HIGH_COLOR;
    if (share > SCORE_MID_RATIO * uniform) return SCORE_MID_COLOR;
    return SCORE_LOW_COLOR;
}

// matplotlib's "jet".
const COLOR_STOPS = [
    [0.0, [0, 0, 143]],
    [0.125, [0, 0, 255]],
    [0.375, [0, 255, 255]],
    [0.625, [255, 255, 0]],
    [0.875, [255, 0, 0]],
    [1.0, [128, 0, 0]],
];

function colorMap(t) {
    const v = Math.max(0, Math.min(1, t));
    for (let i = 0; i < COLOR_STOPS.length - 1; i++) {
        const [p0, c0] = COLOR_STOPS[i];
        const [p1, c1] = COLOR_STOPS[i + 1];
        if (v <= p1) {
            const f = (v - p0) / (p1 - p0 || 1);
            return [
                Math.round(c0[0] + (c1[0] - c0[0]) * f),
                Math.round(c0[1] + (c1[1] - c0[1]) * f),
                Math.round(c0[2] + (c1[2] - c0[2]) * f),
            ];
        }
    }
    return COLOR_STOPS[COLOR_STOPS.length - 1][1];
}

// How much the heat map is upscaled with bicubic before the canvas takes over.
// The canvas itself can only do bilinear, which leaves visible cell squares;
// a 4x Catmull-Rom pass first makes the gradient between cells smooth.
const UPSAMPLE_FACTOR = 4;

function catmullRom(t) {
    const x = Math.abs(t);
    if (x <= 1) return 1.5 * x * x * x - 2.5 * x * x + 1;
    if (x < 2) return -0.5 * x * x * x + 2.5 * x * x - 4 * x + 2;
    return 0;
}

// Mask mode puts the map straight onto the picture's visibility, and a
// linear ramp leaves most of the frame in a flat mid grey where nothing
// reads. A logistic curve pushes the two halves apart: below the midpoint
// goes dark quickly, above it returns to the render.
const MASK_STEEPNESS = 10;
const MASK_MIDPOINT = 0.5;

/** Map 0..1 onto itself through a logistic curve, ends pinned to 0 and 1.
 *
 * Rescaling the logistic affinely is what pins the ends: without it a fully
 * cold cell would still show a little of the render and a fully warm one
 * would still be dimmed.
 */
function maskCurve(value) {
    const s = (v) => 1 / (1 + Math.exp(-MASK_STEEPNESS * (v - MASK_MIDPOINT)));
    const low = s(0);
    const high = s(1);
    return (s(value) - low) / (high - low);
}

/** Bicubic (Catmull-Rom) upsample of a rows x cols map by an integer factor. */
function upsampleBicubic(map, rows, cols, factor) {
    const outRows = rows * factor;
    const outCols = cols * factor;
    const out = new Float32Array(outRows * outCols);

    const clamp = (v, max) => Math.max(0, Math.min(max, v));

    for (let oy = 0; oy < outRows; oy++) {
        const sy = (oy + 0.5) / factor - 0.5;
        const y0 = Math.floor(sy);
        for (let ox = 0; ox < outCols; ox++) {
            const sx = (ox + 0.5) / factor - 0.5;
            const x0 = Math.floor(sx);

            let sum = 0;
            let weight = 0;
            for (let dy = -1; dy <= 2; dy++) {
                const wy = catmullRom(sy - (y0 + dy));
                if (!wy) continue;
                const row = clamp(y0 + dy, rows - 1) * cols;
                for (let dx = -1; dx <= 2; dx++) {
                    const wx = catmullRom(sx - (x0 + dx));
                    if (!wx) continue;
                    sum += map[row + clamp(x0 + dx, cols - 1)] * wy * wx;
                    weight += wy * wx;
                }
            }
            out[oy * outCols + ox] = weight ? sum / weight : 0;
        }
    }

    return out;
}

// Largest smoothing radius, in attention cells, at slider = 1.
const MAX_SMOOTH_CELLS = 1.5;

/** Separable gaussian blur of a rows x cols field, sigma in output pixels. */
function gaussianBlur(map, rows, cols, sigma) {
    if (sigma <= 0) return map;

    const radius = Math.max(1, Math.ceil(sigma * 3));
    const kernel = new Float32Array(radius * 2 + 1);
    let total = 0;
    for (let i = -radius; i <= radius; i++) {
        const w = Math.exp(-(i * i) / (2 * sigma * sigma));
        kernel[i + radius] = w;
        total += w;
    }
    for (let i = 0; i < kernel.length; i++) kernel[i] /= total;

    const clamp = (v, max) => Math.max(0, Math.min(max, v));
    const tmp = new Float32Array(map.length);
    const out = new Float32Array(map.length);

    for (let y = 0; y < rows; y++) {
        const row = y * cols;
        for (let x = 0; x < cols; x++) {
            let sum = 0;
            for (let k = -radius; k <= radius; k++) {
                sum += map[row + clamp(x + k, cols - 1)] * kernel[k + radius];
            }
            tmp[row + x] = sum;
        }
    }
    for (let y = 0; y < rows; y++) {
        for (let x = 0; x < cols; x++) {
            let sum = 0;
            for (let k = -radius; k <= radius; k++) {
                sum += tmp[clamp(y + k, rows - 1) * cols + x] * kernel[k + radius];
            }
            out[y * cols + x] = sum;
        }
    }

    return out;
}

function gradientCss() {
    const stops = COLOR_STOPS.map(
        ([p, [r, g, b]]) => `rgb(${r},${g},${b}) ${Math.round(p * 100)}%`
    );
    // Bottom is low, top is high.
    return `linear-gradient(to top, ${stops.join(", ")})`;
}

/** A labelled 0..1 slider row, with a set() for moving it from code. */
function sliderRow(name, value, onInput) {
    const row = document.createElement("label");
    Object.assign(row.style, {
        display: "flex",
        alignItems: "center",
        gap: "5px",
        marginBottom: "6px",
        color: "#aaa",
    });

    const label = document.createElement("span");
    label.textContent = name;

    const readout = document.createElement("span");
    readout.textContent = value.toFixed(2);
    Object.assign(readout.style, {
        fontVariantNumeric: "tabular-nums",
        minWidth: "30px",
        textAlign: "right",
    });

    const slider = document.createElement("input");
    slider.type = "range";
    slider.min = "0";
    slider.max = "1";
    slider.step = "0.05";
    slider.value = String(value);
    Object.assign(slider.style, { flex: "1 1 auto", minWidth: "0" });
    slider.addEventListener("input", () => {
        const next = parseFloat(slider.value);
        readout.textContent = next.toFixed(2);
        onInput(next);
    });

    row.append(label, slider, readout);

    return {
        row,
        set(next) {
            slider.value = String(next);
            readout.textContent = next.toFixed(2);
        },
    };
}

function viewUrl(entry) {
    const { filename, subfolder, type } = entry || {};
    if (!filename) return null;
    // api.apiURL applies the server's base path and auth, which a bare "/view"
    // string does not.
    return api.apiURL(
        `/view?filename=${encodeURIComponent(filename)}&type=${type}&subfolder=${encodeURIComponent(
            subfolder || ""
        )}`
    );
}

class TagExplorerView {
    constructor(node) {
        this.node = node;

        // (tags, rows, cols) heat maps, kept flat to avoid building nested
        // arrays for what can be tens of thousands of values.
        this.maps = null;
        // Per tag z-scored copy of maps. Tags differ a lot in raw attention
        // magnitude, so comparing them directly lets a globally loud tag win
        // everywhere.
        this.normalized = null;
        this.shape = null;
        this.tags = [];
        // Tag index the pointer is resting on, previewed over the image
        // without disturbing whatever is pinned by clicking.
        this.preview = null;
        // false: jet colours laid over the picture. true: the map becomes
        // the picture's own visibility, which answers "what did this tag
        // actually look at" in the render's own pixels.
        this.mask = false;
        // Overlay strength, plus the value the slider restores per view: it is
        // overlay opacity in heatmap view and how dark the dimming goes in mask
        // view. At 0 either one leaves the render untouched.
        this.alpha = OVERLAY_ALPHA;
        this.alphaFor = { heatmap: OVERLAY_ALPHA, mask: MASK_ALPHA };
        // 0 = raw cells, 1 = heavily smoothed; like wandb's smoothing slider,
        // it filters the values before they are coloured.
        this.smooth = 0.35;
        // Display position the arrow keys are on, into this.order rather
        // than into the tag axis: the list is sorted, the tags are not.
        this.cursor = -1;
        this.order = [];
        this.structure = [];
        this.selected = new Set();
        this.image = null;
        this.rows = [];

        this.buildDom();
    }

    buildDom() {
        const container = document.createElement("div");
        Object.assign(container.style, {
            display: "flex",
            gap: "8px",
            width: "100%",
            height: "100%",
            minHeight: "260px",
            boxSizing: "border-box",
            padding: "4px",
            fontFamily: "Inter, sans-serif",
            fontSize: "11px",
            color: "#e0e0e0",
            overflow: "hidden",
            // Some ComfyUI versions disable pointer events on DOM widgets;
            // without this the canvas never sees a mousemove.
            pointerEvents: "auto",
            // Focusable so the arrow keys can walk the tag list; the focus
            // ring would only outline the whole widget, so it is off.
            outline: "none",
        });
        container.tabIndex = 0;

        const canvasWrap = document.createElement("div");
        Object.assign(canvasWrap.style, {
            flex: "1 1 auto",
            minWidth: "0",
            minHeight: "0",
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "center",
            overflow: "hidden",
        });
        this.canvasWrap = canvasWrap;

        this.canvas = document.createElement("canvas");
        // Sized by fitCanvas(); the element's own width/height stay at the
        // image's pixel resolution.
        Object.assign(this.canvas.style, {
            display: "block",
            cursor: "crosshair",
            borderRadius: "4px",
            pointerEvents: "auto",
        });
        canvasWrap.appendChild(this.canvas);

        // Colour bar: high at the top, low at the bottom, matching COLOR_STOPS.
        const colorbar = document.createElement("div");
        Object.assign(colorbar.style, {
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "3px",
            marginLeft: "6px",
            fontSize: "10px",
            color: "#9a9a9a",
            flex: "0 0 auto",
        });

        const high = document.createElement("div");
        high.textContent = OVERLAY_MAX.toFixed(2);
        const low = document.createElement("div");
        low.textContent = OVERLAY_MIN.toFixed(2);
        for (const label of [high, low]) {
            label.style.fontVariantNumeric = "tabular-nums";
        }

        this.colorbarGradient = document.createElement("div");
        Object.assign(this.colorbarGradient.style, {
            width: "12px",
            flex: "1 1 auto",
            minHeight: "40px",
            borderRadius: "3px",
            border: "1px solid #3a3a3a",
            background: gradientCss(),
        });

        colorbar.appendChild(high);
        colorbar.appendChild(this.colorbarGradient);
        colorbar.appendChild(low);
        canvasWrap.appendChild(colorbar);
        this.colorbar = colorbar;

        this.panel = document.createElement("div");
        Object.assign(this.panel.style, {
            flex: "0 0 210px",
            alignSelf: "stretch",
            overflowY: "auto",
            overflowX: "hidden",
            background: "#1a1a1a",
            border: "1px solid #333",
            borderRadius: "4px",
            padding: "6px",
        });

        this.hint = document.createElement("div");
        this.hint.textContent = "Run the node to load tags.";
        Object.assign(this.hint.style, {
            color: "#888",
            marginBottom: "6px",
            lineHeight: "1.3",
        });
        this.panel.appendChild(this.hint);

        const strength = sliderRow("strength", this.alpha, (value) => {
            this.alpha = value;
            this.alphaFor[this.mask ? "mask" : "heatmap"] = value;
            this.draw();
        });
        this.panel.appendChild(strength.row);

        const smooth = sliderRow("smooth", this.smooth, (value) => {
            this.smooth = value;
            this.draw();
        });
        this.panel.appendChild(smooth.row);

        const viewButton = document.createElement("button");
        Object.assign(viewButton.style, {
            width: "100%",
            marginBottom: "6px",
            padding: "3px 5px",
            background: "#2a2a2a",
            color: "#aaa",
            border: "1px solid #3a3a3a",
            borderRadius: "3px",
            cursor: "pointer",
            font: "inherit",
        });
        const paintView = () => {
            viewButton.textContent = this.mask ? "view: mask" : "view: heatmap";
            viewButton.title = this.mask
                ? "the map dims the picture instead of colouring it; click for the jet overlay"
                : "jet colours over the picture; click to let the map dim the picture instead";
        };
        paintView();
        viewButton.addEventListener("click", () => {
            this.mask = !this.mask;
            this.alpha = this.alphaFor[this.mask ? "mask" : "heatmap"];
            strength.set(this.alpha);
            paintView();
            this.draw();
        });
        viewButton.addEventListener("pointerdown", (e) => e.stopPropagation());
        this.panel.appendChild(viewButton);

        this.list = document.createElement("div");
        this.panel.appendChild(this.list);

        container.appendChild(canvasWrap);
        container.appendChild(this.panel);

        this.container = container;
        this.ctx = this.canvas.getContext("2d");

        // Re-fit whenever the node is resized.
        if (typeof ResizeObserver !== "undefined") {
            this.observer = new ResizeObserver(() => this.fitCanvas());
            this.observer.observe(canvasWrap);
        }

        // Arrow keys walk the list. The widget takes focus as soon as the
        // pointer is over it, so the keys work without a click first.
        container.addEventListener("pointerenter", () => {
            container.focus({ preventScroll: true });
        });
        container.addEventListener("keydown", (e) => {
            const pin = e.key === "Enter" || e.key === " " || e.key === "Spacebar";
            if (e.key !== "ArrowDown" && e.key !== "ArrowUp"
                && e.key !== "Escape" && !pin) {
                return;
            }
            // Neither the page nor the graph canvas should also act on it.
            e.preventDefault();
            e.stopPropagation();

            if (e.key === "Escape") {
                this.preview = null;
                this.cursor = -1;
                this.paintSelection();
                this.draw();
                return;
            }
            if (!this.order.length) return;

            if (pin) {
                if (this.preview !== null) this.toggle(this.preview);
                return;
            }

            const step = e.key === "ArrowDown" ? 1 : -1;
            // From nowhere, down opens at the top and up at the bottom.
            const next = this.cursor < 0
                ? (step > 0 ? 0 : this.order.length - 1)
                : Math.min(this.order.length - 1, Math.max(0, this.cursor + step));

            this.cursor = next;
            this.preview = this.order[next];
            this.rows[this.preview]?.row.scrollIntoView({ block: "nearest" });
            this.paintSelection();
            this.draw();
        });

        // Listen on the wrapper as well: whichever element actually receives the
        // event, the reading is computed from the canvas rect either way.
        const onMove = (e) => this.onHover(e);
        this.canvas.addEventListener("mousemove", onMove);
        this.canvas.addEventListener("click", (e) => this.onClick(e));
        canvasWrap.addEventListener("mousemove", onMove);
        canvasWrap.addEventListener("mouseleave", () => {
            this.updateBars(null);
        });
        // Keep litegraph from panning the graph while interacting.
        this.canvas.addEventListener("pointerdown", (e) => e.stopPropagation());
        this.panel.addEventListener("pointerdown", (e) => e.stopPropagation());
        this.panel.addEventListener("wheel", (e) => e.stopPropagation());
    }

    async setData(message) {
        const tagMapEntry = (message?.tag_maps || [])[0];
        const imageEntry = (message?.tag_images || [])[0];
        this.tags = message?.tags || [];
        this.structure = message?.tag_structure || [];

        if (tagMapEntry) {
            try {
                // Same URL the <img> uses; rebuilding it for fetchApi only
                // risks doubling or dropping the API base path.
                const response = await fetch(viewUrl(tagMapEntry));
                if (!response.ok) {
                    throw new Error(`status ${response.status}`);
                }
                const buffer = await response.arrayBuffer();
                const { data, shape } = await load(buffer);
                this.maps = data;
                this.shape = shape; // [tags, rows, cols]
                this.normalized = this.normalize(data, shape);
            } catch (error) {
                console.error("DAAM: failed to load tag maps", error);
                this.maps = null;
            }
        }

        this.image = imageEntry ? await this.loadImage(viewUrl(imageEntry)) : null;
        if (imageEntry && !this.image) {
            console.error("DAAM: failed to load image", viewUrl(imageEntry));
        }

        this.selected.clear();
        this.buildRows();
        this.draw();
        this.updateBars(null);
    }

    /** Letterbox the canvas into the space the node currently gives it. */
    fitCanvas() {
        if (!this.image || !this.canvasWrap) return;

        const barWidth = this.colorbar ? this.colorbar.offsetWidth + 6 : 0;
        const availableWidth = this.canvasWrap.clientWidth - barWidth;
        const availableHeight = this.canvasWrap.clientHeight;
        if (availableWidth <= 0) return;

        const aspect = this.image.width / this.image.height;

        let width = availableWidth;
        let height = width / aspect;

        // Only constrain by height once the parent actually has one; DOM widget
        // layout can report 0 before the node has been laid out.
        if (availableHeight > 0 && height > availableHeight) {
            height = availableHeight;
            width = height * aspect;
        }

        this.canvas.style.width = `${Math.max(1, Math.floor(width))}px`;
        this.canvas.style.height = `${Math.max(1, Math.floor(height))}px`;

        if (this.colorbar) {
            this.colorbar.style.height = `${Math.max(1, Math.floor(height))}px`;
        }
    }

    /** Z-score each tag's map over its own cells. */
    normalize(data, shape) {
        const [tagCount, rows, cols] = shape;
        const plane = rows * cols;
        const out = new Float32Array(tagCount * plane);

        for (let t = 0; t < tagCount; t++) {
            const base = t * plane;

            let sum = 0;
            for (let i = 0; i < plane; i++) sum += data[base + i];
            const mean = sum / plane;

            let variance = 0;
            for (let i = 0; i < plane; i++) {
                const d = data[base + i] - mean;
                variance += d * d;
            }
            const std = Math.sqrt(variance / plane) || 1e-8;

            for (let i = 0; i < plane; i++) {
                out[base + i] = (data[base + i] - mean) / std;
            }
        }

        return out;
    }

    loadImage(url) {
        return new Promise((resolve) => {
            const img = new Image();
            img.onload = () => resolve(img);
            img.onerror = () => resolve(null);
            img.src = url;
        });
    }

    buildRows() {
        this.list.innerHTML = "";

        if (!this.image) {
            this.hint.textContent = "Could not load the image (see console).";
        } else {
            this.hint.textContent = this.tags.length
                ? "Bars say whether a tag gave the picture a shape, sharply or broadly, against fixed thresholds rather than against each other. Point at a tag to see its map, click to pin."
                : "No tags found.";
        }

        // Strongest first: the tags worth looking at should not be buried
        // in the middle of the prompt order.
        const order = this.tags.map((_, index) => index);
        const score = (index) => this.structure[index] ?? -Infinity;
        if (this.structure.length) order.sort((a, b) => score(b) - score(a));

        this.order = order;
        this.cursor = -1;
        this.rows = new Array(this.tags.length);
        for (const index of order) {
            const tag = this.tags[index];
            const row = document.createElement("div");
            Object.assign(row.style, {
                position: "relative",
                padding: "3px 5px",
                marginBottom: "2px",
                borderRadius: "3px",
                cursor: "pointer",
                overflow: "hidden",
                border: "1px solid transparent",
            });

            const bar = document.createElement("div");
            Object.assign(bar.style, {
                position: "absolute",
                left: "0",
                top: "0",
                bottom: "0",
                width: "0%",
                background: SCORE_LOW_COLOR,
                opacity: "0.25",
                transition: "width 0.05s linear",
            });

            const label = document.createElement("span");
            label.textContent = tag;
            Object.assign(label.style, {
                position: "relative",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
                display: "inline-block",
                maxWidth: "140px",
                verticalAlign: "middle",
            });

            const value = document.createElement("span");
            value.textContent = "0.00";
            Object.assign(value.style, {
                position: "relative",
                float: "right",
                opacity: "0.7",
                fontVariantNumeric: "tabular-nums",
            });

            row.appendChild(bar);
            row.appendChild(label);
            row.appendChild(value);

            row.addEventListener("click", () => this.toggle(index));
            // Pointing at a row is enough to see it; clicking pins it so
            // several tags can be shown together.
            row.addEventListener("mouseenter", () => {
                this.preview = index;
                this.cursor = order.indexOf(index);
                this.paintSelection();
                this.draw();
            });
            row.addEventListener("mouseleave", () => {
                if (this.preview === index) {
                    this.preview = null;
                    this.paintSelection();
                    this.draw();
                }
            });

            this.list.appendChild(row);
            // Keyed by tag index, not by position, so every other reading
            // stays aligned with the token axis while the list is sorted.
            this.rows[index] = { row, bar, label, value };
        }

        this.paintSelection();
    }

    toggle(index) {
        if (this.selected.has(index)) {
            this.selected.delete(index);
        } else {
            this.selected.add(index);
        }
        this.paintSelection();
        this.draw();
    }

    paintSelection() {
        this.rows.forEach(({ row }, index) => {
            const on = this.selected.has(index);
            // The keyboard cursor is a dotted outline, so it reads as "this
            // is where the arrows are" rather than as another pinned tag.
            const at = index === this.preview;
            row.style.border = on
                ? `1px solid ${SCORE_HIGH_COLOR}`
                : at ? "1px dotted #9a9a9a" : "1px solid transparent";
            row.style.background = on ? "rgba(106, 176, 255, 0.12)" : "transparent";
        });
    }

    /** Per tag share at one cell: softmax over the z-scored tag maps. */
    sharesAt(row, col) {
        if (!this.normalized || !this.shape) return null;

        const [tagCount, rows, cols] = this.shape;
        if (row < 0 || col < 0 || row >= rows || col >= cols) return null;

        const plane = rows * cols;
        const offset = row * cols + col;

        let max = -Infinity;
        for (let t = 0; t < tagCount; t++) {
            const v = this.normalized[t * plane + offset];
            if (v > max) max = v;
        }

        const values = new Float32Array(tagCount);
        let total = 0;
        for (let t = 0; t < tagCount; t++) {
            const v = Math.exp(this.normalized[t * plane + offset] - max);
            values[t] = v;
            total += v;
        }
        if (!(total > 0)) return null;

        for (let t = 0; t < tagCount; t++) values[t] /= total;
        return values;
    }

    /** Map a mouse event to a heat map cell, or null outside the image. */
    cellAt(event) {
        if (!this.shape || !this.image) return null;

        const rect = this.canvas.getBoundingClientRect();
        const x = (event.clientX - rect.left) / rect.width;
        const y = (event.clientY - rect.top) / rect.height;

        if (x < 0 || x > 1 || y < 0 || y > 1) return null;

        const [, rows, cols] = this.shape;
        return {
            row: Math.min(rows - 1, Math.max(0, Math.floor(y * rows))),
            col: Math.min(cols - 1, Math.max(0, Math.floor(x * cols))),
        };
    }

    onHover(event) {
        const cell = this.cellAt(event);
        this.updateBars(cell ? this.sharesAt(cell.row, cell.col) : null);
    }

    /** Clicking the image selects the tag that dominates that spot. */
    onClick(event) {
        const cell = this.cellAt(event);
        if (!cell) return;

        const shares = this.sharesAt(cell.row, cell.col);
        if (!shares) return;

        let best = 0;
        for (let i = 1; i < shares.length; i++) {
            if (shares[i] > shares[best]) best = i;
        }

        // Plain click shows just that tag; ctrl/shift-click adds it to the
        // current selection like clicking its row would.
        if (event.ctrlKey || event.shiftKey || event.metaKey) {
            this.selected.add(best);
        } else {
            this.selected.clear();
            this.selected.add(best);
        }

        this.paintSelection();
        this.draw();
        this.rows[best]?.row.scrollIntoView({ block: "nearest" });
    }

    updateBars(shares) {
        if (shares) {
            this.rows.forEach(({ bar, label, value }, index) => {
                const share = shares[index];
                const color = tierColor(share, this.rows.length);
                bar.style.width = `${Math.min(100, share * 100)}%`;
                bar.style.background = color;
                bar.style.opacity = "0.25";
                label.style.color = color;
                value.textContent = share.toFixed(2);
            });
            return;
        }

        // Off the image the bars stand for whether each tag gave the picture
        // a shape at all, scored 0..1 by the node against fixed thresholds, so
        // the panel opens on what the render actually built.
        this.rows.forEach(({ bar, label, value }, index) => {
            const z = this.structure[index];
            if (z === undefined) {
                bar.style.width = "0%";
                value.textContent = "";
                label.style.color = "#e0e0e0";
                return;
            }

            const color = z >= LANDED_CLEAR
                ? SCORE_HIGH_COLOR
                : z > LANDED_AT_ALL ? SCORE_MID_COLOR : SCORE_LOW_COLOR;

            bar.style.width = `${Math.min(100, Math.max(0, z) * 100)}%`;
            bar.style.background = color;
            bar.style.opacity = "0.22";
            label.style.color = color;
            value.textContent = z.toFixed(2);
        });
    }

    /** Union of the individually normalised maps of whatever is showing.
     *
     * Cellwise max, not a mean: two tags rarely look at the same place, so
     * averaging would put roughly one map at 1 and the rest at 0 in any given
     * cell and cap the result near 1/N -- three tags and everything goes cold
     * even though each one on its own was bright. Max keeps every tag at the
     * scale it had alone, which is also what makes the colorbar mean the same
     * thing however many tags are pinned. With one tag showing the two agree.
     *
     * The pointer wins over the pinned selection while it is on a row, so
     * running down the list plays the tags back one after another.
     */
    selectedMap() {
        if (!this.normalized || !this.shape) return null;

        const showing = this.preview === null
            ? this.selected
            : new Set([this.preview]);
        if (showing.size === 0) return null;

        const [, rows, cols] = this.shape;
        const plane = rows * cols;
        const out = new Float32Array(plane);

        for (const index of showing) {
            const base = index * plane;
            const slice = this.normalized.subarray(base, base + plane);

            // Normalise each tag before combining so a single high magnitude
            // tag cannot drown out the others.
            let min = Infinity;
            let max = -Infinity;
            for (let i = 0; i < plane; i++) {
                const v = slice[i];
                if (v < min) min = v;
                if (v > max) max = v;
            }
            const range = max - min || 1;
            for (let i = 0; i < plane; i++) {
                const v = Math.max(0, Math.min(1, (slice[i] - min) / range));
                if (v > out[i]) out[i] = v;
            }
        }

        return out;
    }

    draw() {
        if (!this.image) return;

        const { width, height } = this.image;
        this.canvas.width = width;
        this.canvas.height = height;

        this.fitCanvas();

        // Compose into an offscreen canvas so a redraw is one blit, instead
        // of redoing the bicubic upsample every time.
        this.composed = document.createElement("canvas");
        this.composed.width = width;
        this.composed.height = height;
        const ctx = this.composed.getContext("2d");

        const map = this.selectedMap();

        ctx.globalAlpha = 1;
        ctx.drawImage(this.image, 0, 0, width, height);

        if (!map || !this.shape) {
            this.present();
            return;
        }

        const [, rows, cols] = this.shape;
        // Bicubic first when smoothing: the canvas itself can only interpolate
        // bilinearly, which shows the cell grid. With smoothing off the raw
        // cells are drawn as flat squares -- the honest view of the data.
        const factor = this.smooth > 0 ? UPSAMPLE_FACTOR : 1;
        const upRows = rows * factor;
        const upCols = cols * factor;
        let values = map;
        if (this.smooth > 0) {
            values = upsampleBicubic(map, rows, cols, UPSAMPLE_FACTOR);
            // Sigma grows with the slider, measured in cells.
            const sigma = this.smooth * MAX_SMOOTH_CELLS * UPSAMPLE_FACTOR;
            values = gaussianBlur(values, upRows, upCols, sigma);
        }

        const small = document.createElement("canvas");
        small.width = upCols;
        small.height = upRows;
        const smallCtx = small.getContext("2d");
        const imageData = smallCtx.createImageData(upCols, upRows);

        for (let i = 0; i < upRows * upCols; i++) {
            const value = values[i];
            if (this.mask) {
                // Black paint whose opacity is what the map did NOT give the
                // cell, so 1 leaves the render untouched and 0 blacks it out.
                const shown = maskCurve(Math.max(0, Math.min(1, value)));
                imageData.data[i * 4 + 3] = Math.round(255 * (1 - shown));
                continue;
            }
            const [r, g, b] = colorMap(value);
            imageData.data[i * 4] = r;
            imageData.data[i * 4 + 1] = g;
            imageData.data[i * 4 + 2] = b;
            imageData.data[i * 4 + 3] = 255;
        }
        smallCtx.putImageData(imageData, 0, 0);

        // In mask view the overlay is black paint, so the same alpha reads as
        // how far the cold half is allowed to go down.
        ctx.globalAlpha = this.alpha;
        ctx.imageSmoothingEnabled = this.smooth > 0;
        ctx.imageSmoothingQuality = "high";
        ctx.drawImage(small, 0, 0, width, height);
        ctx.globalAlpha = 1;
        ctx.imageSmoothingEnabled = true;

        this.present();
    }

    /** Blit the composition built by draw(). */
    present() {
        if (!this.composed) return;

        this.ctx.globalAlpha = 1;
        this.ctx.drawImage(this.composed, 0, 0);
    }
}

app.registerExtension({
    name: "comfyui_daam_pack.daam_tag_explorer",

    async nodeCreated(node) {
        if (node?.comfyClass !== "DAAMTagExplorer") return;

        const view = new TagExplorerView(node);
        node._daamTagExplorer = view;

        node.addDOMWidget("daam_tag_explorer", "div", view.container, {
            serialize: false,
            hideOnZoom: false,
        });

        if (node.size[0] < 640) node.size[0] = 640;
        if (node.size[1] < 420) node.size[1] = 420;

        const onExecuted = node.onExecuted;
        node.onExecuted = function (message) {
            onExecuted?.apply(this, arguments);

            // This node draws its own canvas, so clear any preview litegraph
            // is still holding from an earlier run.
            this.imgs = [];
            this.images = [];

            view.setData(message);
        };
    },
});
