class Canvas {
  constructor(options = {}) {
    // Canvas elements
    this.canvas = options.canvas || document.getElementById("whiteboard");
    if (!this.canvas) {
      throw new Error("Canvas element is required");
    }

    this.ctx = this.canvas.getContext("2d", {
      desynchronized: true, // Reduce latency
      alpha: false, // Optimize performance
    });

    if (!this.ctx) {
      throw new Error("Could not get canvas context");
    }

    this.container = options.container || document.getElementById("container");

    // Status display handling
    if (typeof options.showStatus === "function") {
      // If a function is provided, use it
      this.statusDisplayFn = options.showStatus;
    } else {
      // Otherwise, look for a DOM element
      this.statusDisplay = options.statusDisplay || null;
    }

    // Readonly mode
    this.readonly = options.readonly || false;

    // External UI update function
    this.externalUpdateUIControls = options.updateUIControls || null;

    // Field dimensions (fixed size we want to display)
    this.FIELD_WIDTH = 800;
    this.FIELD_HEIGHT = 400;

    // Background image
    this.backgroundImage = new Image();
    this.backgroundImage.src = options.backgroundImage || "";
    this.backgroundLoaded = false;
    this.backgroundImage.onload = () => {
      this.backgroundLoaded = true;
      this.resetView(); // Center and scale the view when image loads
      this.redrawCanvas();
    };

    // Safety limits
    this.MAX_STROKES = 10000; // Prevent memory issues
    this.MIN_SCALE = 0.1;
    this.MAX_SCALE = 10;
    this.lastDPR = window.devicePixelRatio || 1;

    // Drawing state
    this.isDrawing = false;
    this.previewShape = null; // Add preview shape state

    // Pan and zoom state
    this.isPanning = false;
    this.startPanX = 0;
    this.startPanY = 0;
    this.offsetX = 0;
    this.offsetY = 0;
    this.scale = 1;
    this.lastDistance = null;

    // Pan limits - how far from center user can pan
    this.MAX_PAN_DISTANCE = options.maxPanDistance || 500;

    // Flip and Rotate state
    this.flipX = false;
    this.flipY = false;
    this.rotation = 0; // Rotation angle in degrees (0, 90, 180, 270)

    // Grid settings
    this.GRID_SPACING = options.gridSpacing || 50;
    this.GRID_COLOR = options.gridColor || "#e0e0e0";
    this.AXIS_COLOR = options.axisColor || "#a0a0a0";

    // Line style
    this.currentColor = options.initialColor || "#000000";
    this.currentThickness = options.initialThickness || 3;
    this.isFilled = false; // Add fill state

    // Drawing history for undo and save functionality
    this.drawingHistory = [];
    this.redoHistory = []; // Add redo history
    this.currentStroke = [];

    // Current tool state
    this.currentTool = "pen"; // pen, rectangle, circle, line, hexagon, star, arrow, select
    this.startX = null;
    this.startY = null;

    // Selection state
    this.selectedStrokes = [];
    this.selectionRect = null;
    this.isSelecting = false;
    this.selectedStrokesCopy = null; // For copy/cut operations
    this.moveSelection = {
      active: false,
      startX: 0,
      startY: 0,
      offsetX: 0,
      offsetY: 0,
    };

    // Initialize LocalForage
    this.storage = localforage.createInstance({
      name: "CanvasField",
    });

    // Perfect freehand settings
    this.thinning = 0.5;
    this.smoothing = 0.5;

    // Auto-save interval (every 30 seconds)
    this.autoSaveInterval = setInterval(() => this.autoSave(), 30000);

    // Initialize
    this.resizeCanvas();
    this.bindEvents();

    // Handle DPR changes (e.g., moving between monitors)
    this.dprMediaQuery = matchMedia(
      `(resolution: ${window.devicePixelRatio}dppx)`,
    );
    this.dprMediaQuery.addEventListener("change", () => {
      if (this.lastDPR !== (window.devicePixelRatio || 1)) {
        this.lastDPR = window.devicePixelRatio || 1;
        this.resizeCanvas();
      }
    });

    // Handle context loss
    this.canvas.addEventListener("webglcontextlost", (e) => {
      e.preventDefault();
      this.showStatus("Canvas context lost - Attempting to restore...");
    });

    this.canvas.addEventListener("webglcontextrestored", () => {
      this.showStatus("Canvas restored");
      this.resizeCanvas();
    });

    // Add resize handle state
    this.resizeHandles = {
      active: false,
      activeHandle: null,
      size: 8,
      positions: [],
    };
  }

  // Add new method to reset view
  resetView() {
    const rect = this.container.getBoundingClientRect();
    const containerWidth = rect.width;
    const containerHeight = rect.height;
    const dpr = window.devicePixelRatio || 1;

    // Calculate scale to fit the field in the container, accounting for DPR
    const scaleX = (containerWidth * dpr) / this.FIELD_WIDTH;
    const scaleY = (containerHeight * dpr) / this.FIELD_HEIGHT;
    this.scale = Math.min(scaleX, scaleY) * 0.95; // 95% to add a small margin

    // Center the field, accounting for DPR
    this.offsetX = (containerWidth * dpr) / 2;
    this.offsetY = (containerHeight * dpr) / 2;
  }

  resizeCanvas() {
    // Get the container's CSS dimensions
    const rect = this.container.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;

    // Set canvas dimensions to match container size, accounting for device pixel ratio
    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;

    // Set CSS size explicitly
    this.canvas.style.width = `${rect.width}px`;
    this.canvas.style.height = `${rect.height}px`;

    // Always reset view to ensure proper centering
    this.resetView();

    // Apply pan limits after resize
    this.applyPanLimits();

    // Redraw with updated dimensions
    this.redrawCanvas();

    return {
      width: rect.width,
      height: rect.height,
    };
  }

  // Drawing functions
  drawStroke(stroke, isSelected = false) {
    if (!Array.isArray(stroke) || stroke.length < 2) {
      return;
    }

    try {
      const strokePoints = this.getStrokePoints(stroke);
      if (!strokePoints || strokePoints.length < 2) {
        return;
      }

      this.ctx.beginPath();
      this.ctx.moveTo(strokePoints[0].x, strokePoints[0].y);

      // Draw using cubic Bézier curves for smoother lines
      for (let i = 0; i < strokePoints.length - 1; i++) {
        const current = strokePoints[i];
        const next = strokePoints[i + 1];

        if (!current || !next) {
          continue;
        } // Skip if points are invalid

        if (current.ctrl1x !== undefined) {
          // Use cubic Bézier if we have control points
          this.ctx.bezierCurveTo(
            current.ctrl1x,
            current.ctrl1y,
            current.ctrl2x,
            current.ctrl2y,
            next.x,
            next.y,
          );
        } else {
          // Fallback to quadratic curve
          const xc = (current.x + next.x) / 2;
          const yc = (current.y + next.y) / 2;
          this.ctx.quadraticCurveTo(current.x, current.y, xc, yc);
        }

        this.ctx.lineWidth = current.thickness || this.currentThickness;
      }

      // Draw selection highlight if selected (draw it first as a background)
      if (isSelected) {
        this.ctx.save();
        this.ctx.strokeStyle = "#0066ff";
        // Cap the highlight thickness to a maximum of 4px more than the stroke
        const highlightThickness = Math.min(
          stroke[0].thickness + 4,
          stroke[0].thickness * 1.2,
        );
        this.ctx.lineWidth = highlightThickness;
        this.ctx.setLineDash([]);
        this.ctx.globalAlpha = 0.3;
        this.ctx.stroke();
        this.ctx.restore();
      }

      // Draw the actual stroke
      this.ctx.strokeStyle = stroke[0].color || this.currentColor;
      this.ctx.lineCap = "round";
      this.ctx.lineJoin = "round";
      this.ctx.stroke();

      // Draw a second highlight for better visibility
      if (isSelected) {
        this.ctx.save();
        this.ctx.strokeStyle = "#ffffff";
        // Cap the inner highlight thickness to a maximum of 2px more than the stroke
        const innerHighlightThickness = Math.min(
          stroke[0].thickness + 2,
          stroke[0].thickness * 1.1,
        );
        this.ctx.lineWidth = innerHighlightThickness;
        this.ctx.setLineDash([]);
        this.ctx.globalAlpha = 0.5;
        this.ctx.stroke();
        this.ctx.restore();
      }
    } catch (error) {
      console.warn("Error drawing stroke:", error);
    }
  }

  // Draw coordinate grid and axes
  drawGridAndAxes() {
    const canvasWidth = this.canvas.width;
    const canvasHeight = this.canvas.height;

    // Calculate grid boundaries based on view size and pan limit
    const boundsLeft = -this.MAX_PAN_DISTANCE * 2;
    const boundsRight = canvasWidth + this.MAX_PAN_DISTANCE * 2;
    const boundsTop = -this.MAX_PAN_DISTANCE * 2;
    const boundsBottom = canvasHeight + this.MAX_PAN_DISTANCE * 2;

    // Calculate grid start coordinates
    const startX =
      Math.floor(boundsLeft / this.GRID_SPACING) * this.GRID_SPACING;
    const startY =
      Math.floor(boundsTop / this.GRID_SPACING) * this.GRID_SPACING;

    // Calculate number of lines needed
    const numHorizontalLines =
      Math.ceil((boundsBottom - boundsTop) / this.GRID_SPACING) + 1;
    const numVerticalLines =
      Math.ceil((boundsRight - boundsLeft) / this.GRID_SPACING) + 1;

    // Save current drawing state
    this.ctx.save();

    // Set line style for grid
    this.ctx.lineWidth = 1;
    this.ctx.strokeStyle = this.GRID_COLOR;

    // Draw horizontal grid lines
    for (let i = 0; i < numHorizontalLines; i++) {
      const y = startY + i * this.GRID_SPACING;
      this.ctx.beginPath();
      this.ctx.moveTo(boundsLeft, y);
      this.ctx.lineTo(boundsRight, y);
      this.ctx.stroke();
    }

    // Draw vertical grid lines
    for (let i = 0; i < numVerticalLines; i++) {
      const x = startX + i * this.GRID_SPACING;
      this.ctx.beginPath();
      this.ctx.moveTo(x, boundsTop);
      this.ctx.lineTo(x, boundsBottom);
      this.ctx.stroke();
    }

    // Draw coordinate axes
    this.ctx.strokeStyle = this.AXIS_COLOR;
    this.ctx.lineWidth = 2;

    // X-axis
    this.ctx.beginPath();
    this.ctx.moveTo(boundsLeft, 0);
    this.ctx.lineTo(boundsRight, 0);
    this.ctx.stroke();

    // Y-axis
    this.ctx.beginPath();
    this.ctx.moveTo(0, boundsTop);
    this.ctx.lineTo(0, boundsBottom);
    this.ctx.stroke();

    // Draw axis labels
    this.ctx.fillStyle = this.AXIS_COLOR;
    this.ctx.font = "12px Arial";
    this.ctx.textAlign = "center";
    this.ctx.textBaseline = "top";

    // X-axis labels
    for (let x = this.GRID_SPACING; x <= boundsRight; x += this.GRID_SPACING) {
      this.ctx.fillText(x.toString(), x, 5);
      if (x !== 0) {
        this.ctx.fillText((-x).toString(), -x, 5);
      }
    }

    // Y-axis labels
    this.ctx.textAlign = "right";
    this.ctx.textBaseline = "middle";
    for (let y = this.GRID_SPACING; y <= boundsBottom; y += this.GRID_SPACING) {
      this.ctx.fillText(y.toString(), -5, y);
      if (y !== 0) {
        this.ctx.fillText((-y).toString(), -5, -y);
      }
    }

    // Draw origin label
    this.ctx.textAlign = "right";
    this.ctx.textBaseline = "top";
    this.ctx.fillText("0", -5, 5);

    // Restore drawing state
    this.ctx.restore();
  }

  // Apply pan limits to prevent going too far from center
  applyPanLimits() {
    const centerX = this.canvas.width / 2;
    const centerY = this.canvas.height / 2;

    // Calculate distance from center
    const dx = this.offsetX - centerX;
    const dy = this.offsetY - centerY;
    const distance = Math.sqrt(dx * dx + dy * dy);

    // If beyond limit, scale back
    if (distance > this.MAX_PAN_DISTANCE) {
      const ratio = this.MAX_PAN_DISTANCE / distance;
      this.offsetX = centerX + dx * ratio;
      this.offsetY = centerY + dy * ratio;
    }
  }

  redrawCanvas() {
    // Ensure canvas context is valid
    if (!this.ctx) {
      this.ctx = this.canvas.getContext("2d", {
        desynchronized: true,
        alpha: false,
      });
      if (!this.ctx) {
        this.showStatus("Error: Could not restore canvas context");
        return;
      }
    }

    this.ctx.setTransform(1, 0, 0, 1, 0, 0); // Reset transform

    // Set white background
    this.ctx.fillStyle = "#ffffff";
    this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

    // Apply transformations with safety checks
    const safeOffsetX = isFinite(this.offsetX) ? this.offsetX : 0;
    const safeOffsetY = isFinite(this.offsetY) ? this.offsetY : 0;
    this.ctx.translate(safeOffsetX, safeOffsetY);

    // Apply scale for drawing with safety check
    const safeScale = Math.min(
      Math.max(this.scale, this.MIN_SCALE),
      this.MAX_SCALE,
    );
    if (this.scale !== safeScale) {
      this.scale = safeScale;
      this.showStatus(`Scale limited to ${this.scale.toFixed(2)}`);
    }
    this.ctx.scale(this.scale, this.scale);

    // Apply flip transformations
    if (this.flipX) {
      this.ctx.scale(-1, 1);
    }
    if (this.flipY) {
      this.ctx.scale(1, -1);
    }

    // Apply rotation
    if (this.rotation !== 0) {
      const rotationRadians = (this.rotation * Math.PI) / 180;
      this.ctx.rotate(rotationRadians);
    }

    // Draw the field image first if loaded
    if (this.backgroundLoaded) {
      const x = -this.FIELD_WIDTH / 2;
      const y = -this.FIELD_HEIGHT / 2;
      this.ctx.drawImage(
        this.backgroundImage,
        x,
        y,
        this.FIELD_WIDTH,
        this.FIELD_HEIGHT,
      );
    }

    // Draw all strokes from history with length limit
    if (this.drawingHistory.length > this.MAX_STROKES) {
      this.drawingHistory = this.drawingHistory.slice(-this.MAX_STROKES);
      this.showStatus(`Drawing history limited to ${this.MAX_STROKES} strokes`);
    }

    // Draw non-selected strokes normally
    this.drawingHistory.forEach((stroke, index) => {
      if (!this.selectedStrokes.includes(index)) {
        try {
          if (Array.isArray(stroke) && stroke[0].type) {
            // It's a shape
            this.drawShape(stroke[0]);
          } else {
            // It's a freehand stroke
            this.drawStroke(stroke);
          }
        } catch (error) {
          console.error("Error drawing stroke:", error);
        }
      }
    });

    // Draw selected strokes with highlight
    this.ctx.save();
    this.ctx.strokeStyle = "#0066ff";
    this.ctx.lineWidth = 2;
    this.selectedStrokes.forEach((index) => {
      const stroke = this.drawingHistory[index];
      try {
        if (Array.isArray(stroke) && stroke[0].type) {
          // It's a shape
          this.drawShape(stroke[0], false, true);
        } else {
          // It's a freehand stroke
          this.drawStroke(stroke, true);
        }
      } catch (error) {
        console.error("Error drawing selected stroke:", error);
      }
    });
    this.ctx.restore();

    // Draw current stroke if active
    if (this.currentStroke.length > 0) {
      try {
        this.drawStroke(this.currentStroke);
      } catch (error) {
        console.error("Error drawing current stroke:", error);
      }
    }

    // Draw preview shape if exists
    if (this.previewShape) {
      try {
        this.drawShape(this.previewShape, true);
      } catch (error) {
        console.error("Error drawing preview shape:", error);
      }
    }

    // Draw selection rectangle if selecting
    if (this.selectionRect && this.currentTool === "select") {
      this.ctx.save();
      this.ctx.strokeStyle = "#0066ff";
      this.ctx.lineWidth = 1;
      this.ctx.setLineDash([5, 5]);
      this.ctx.strokeRect(
        this.selectionRect.x,
        this.selectionRect.y,
        this.selectionRect.width,
        this.selectionRect.height,
      );
      this.ctx.restore();
    }

    // After drawing selection rectangle, add resize handles
    if (
      this.selectionRect &&
      this.currentTool === "select" &&
      !this.isSelecting
    ) {
      this.drawResizeHandles();
    }
  }

  getTransformedPosition(clientX, clientY) {
    // Safety check for input values
    if (!isFinite(clientX) || !isFinite(clientY)) {
      return { x: 0, y: 0 };
    }

    // Get the canvas bounds
    const rect = this.canvas.getBoundingClientRect();

    // Calculate the scale between CSS pixels and canvas pixels
    const cssScale = rect.width / this.canvas.width;

    // Convert screen coordinates to canvas coordinates, accounting for CSS scaling
    const canvasX = (clientX - rect.left) / cssScale;
    const canvasY = (clientY - rect.top) / cssScale;

    // Apply the transformation for pan and zoom with safety checks
    const safeOffsetX = isFinite(this.offsetX) ? this.offsetX : 0;
    const safeOffsetY = isFinite(this.offsetY) ? this.offsetY : 0;
    const safeScale = Math.min(
      Math.max(this.scale, this.MIN_SCALE),
      this.MAX_SCALE,
    );

    let x = (canvasX - safeOffsetX) / safeScale;
    let y = (canvasY - safeOffsetY) / safeScale;

    // The forward transform in redrawCanvas is:
    //   translate(offset) -> scale(zoom) -> flip -> rotate
    // Which means a drawing-space point p maps to screen as:
    //   screen = T(S(Flip(R(p))))
    // After undoing T and S above, the remaining value is Flip(R(p)).
    // To recover point we need: p = R⁻¹(Flip⁻¹(value))
    // So: apply inverse-flip first, then inverse-rotation.

    // 1. Apply inverse flip (flip is its own inverse)
    if (this.flipX) {
      x = -x;
    }
    if (this.flipY) {
      y = -y;
    }

    // 2. Apply inverse rotation
    if (this.rotation !== 0) {
      const rotationRadians = (-this.rotation * Math.PI) / 180;
      const cos = Math.cos(rotationRadians);
      const sin = Math.sin(rotationRadians);
      const rx = x * cos - y * sin;
      const ry = x * sin + y * cos;
      x = rx;
      y = ry;
    }

    // Ensure returned coordinates are finite
    return {
      x: isFinite(x) ? x : 0,
      y: isFinite(y) ? y : 0,
    };
  }

  // Status message
  showStatus(message) {
    // If we have a status display function from options, use it
    if (typeof this.statusDisplayFn === "function") {
      this.statusDisplayFn(message);
      return;
    }

    // If statusDisplay element exists, update it
    if (
      this.statusDisplay &&
      typeof this.statusDisplay.textContent !== "undefined"
    ) {
      this.statusDisplay.textContent = message;
      // Clear the message after 3 seconds
      setTimeout(() => {
        this.statusDisplay.textContent = "";
      }, 3000);
    } else {
      // Just log to console if no status display is available
      console.log(message);
    }
  }

  // Action methods
  undo() {
    if (this.drawingHistory.length === 0) {
      this.showStatus("Nothing to undo");
      return false;
    }

    const lastOp = this.drawingHistory.pop();

    if (lastOp.type === "colorChange") {
      // Reverse the color change
      lastOp.strokes.forEach(({ index, oldColor }) => {
        const stroke = this.drawingHistory[index];
        if (Array.isArray(stroke)) {
          stroke.forEach((point) => (point.color = oldColor));
        } else if (stroke[0]?.type) {
          stroke[0].color = oldColor;
        }
      });
      this.redoHistory.push(lastOp);
      this.redrawCanvas();
    } else if (lastOp.type === "thicknessChange") {
      // Reverse the thickness change
      lastOp.strokes.forEach(({ index, oldThickness }) => {
        const stroke = this.drawingHistory[index];
        if (Array.isArray(stroke)) {
          stroke.forEach((point) => (point.thickness = oldThickness));
        } else if (stroke[0]?.type) {
          stroke[0].thickness = oldThickness;
        }
      });
      this.redoHistory.push(lastOp);
      this.redrawCanvas();
    } else if (lastOp.type === "fillChange") {
      // Reverse the fill change
      lastOp.strokes.forEach(({ index, oldFill }) => {
        const stroke = this.drawingHistory[index];
        if (stroke[0]?.type) {
          stroke[0].isFilled = oldFill;
        }
      });
      this.redoHistory.push(lastOp);
      this.redrawCanvas();
    } else if (lastOp.type === "move") {
      // Reverse the move
      for (const index of lastOp.strokes) {
        const stroke = this.drawingHistory[index];
        if (Array.isArray(stroke)) {
          stroke.forEach((point) => {
            point.x -= lastOp.dx;
            point.y -= lastOp.dy;
          });
        } else if (stroke[0]?.type) {
          stroke[0].x -= lastOp.dx;
          stroke[0].y -= lastOp.dy;
        }
      }
      this.redoHistory.push(lastOp);
      this.redrawCanvas();
    } else if (lastOp.type === "delete") {
      // Restore deleted strokes
      lastOp.strokes.reverse().forEach(({ index, stroke }) => {
        this.drawingHistory.splice(index, 0, stroke);
      });
      this.selectedStrokes = lastOp.strokes.map((s) => s.index);
      this.redoHistory.push(lastOp);
      this.redrawCanvas();
    } else if (lastOp.type === "paste") {
      // Remove pasted strokes
      const indices = lastOp.newStrokes
        .map((s) => s.index)
        .sort((a, b) => b - a);
      indices.forEach((index) => {
        this.drawingHistory.splice(index, 1);
      });
      this.selectedStrokes = [];
      this.redoHistory.push(lastOp);
      this.redrawCanvas();
    } else {
      // Regular stroke or shape
      this.redoHistory.push(lastOp);
      this.redrawCanvas();
    }

    this.showStatus("Undo successful");
    return true;
  }

  redo() {
    if (this.redoHistory.length === 0) {
      this.showStatus("Nothing to redo");
      return false;
    }

    const nextOp = this.redoHistory.pop();

    if (nextOp.type === "move") {
      // Reapply the move
      for (const index of nextOp.strokes) {
        const stroke = this.drawingHistory[index];
        if (Array.isArray(stroke)) {
          stroke.forEach((point) => {
            point.x += nextOp.dx;
            point.y += nextOp.dy;
          });
        } else if (stroke[0]?.type) {
          stroke[0].x += nextOp.dx;
          stroke[0].y += nextOp.dy;
        }
      }
      this.drawingHistory.push(nextOp);
      this.redrawCanvas();
    } else if (nextOp.type === "delete") {
      // Reapply deletion
      const sortedIndices = nextOp.strokes
        .map((s) => s.index)
        .sort((a, b) => b - a);
      sortedIndices.forEach((index) => {
        this.drawingHistory.splice(index, 1);
      });
      this.selectedStrokes = [];
      this.drawingHistory.push(nextOp);
      this.redrawCanvas();
    } else if (nextOp.type === "paste") {
      // Restore pasted strokes
      nextOp.newStrokes.forEach(({ index, stroke }) => {
        this.drawingHistory.splice(index, 0, stroke);
      });
      this.selectedStrokes = nextOp.newStrokes.map((s) => s.index);
      this.drawingHistory.push(nextOp);
      this.redrawCanvas();
    } else {
      // Regular stroke or shape
      this.drawingHistory.push(nextOp);
      this.redrawCanvas();
    }

    this.showStatus("Redo successful");
    return true;
  }

  setTool(tool) {
    if (this.readonly) {
      this.showStatus("Cannot change tool in read-only mode");
      return;
    }
    this.currentTool = tool;
    this.selectedStrokes = [];
    this.selectionRect = null;
    this.canvas.style.cursor = "default";
  }

  setFill(filled) {
    if (this.readonly) {
      this.showStatus("Cannot change fill in read-only mode");
      return;
    }
    this.isFilled = filled;
    // Update fill of selected shapes
    if (this.selectedStrokes.length > 0) {
      // Create fill change operation
      const fillOp = {
        type: "fillChange",
        strokes: this.selectedStrokes.map((index) => ({
          index,
          oldFill: this.drawingHistory[index][0].isFilled,
          newFill: filled,
        })),
      };

      // Update fills
      this.selectedStrokes.forEach((index) => {
        const stroke = this.drawingHistory[index];
        if (stroke[0]?.type) {
          // Only update shapes, not freehand strokes
          stroke[0].isFilled = filled;
        }
      });

      // Add operation to history
      this.drawingHistory.push(fillOp);
      this.redoHistory = [];
      this.redrawCanvas();
      this.showStatus("Fill updated for selection");
    }
  }

  setColor(color) {
    if (this.readonly) {
      this.showStatus("Cannot change color in read-only mode");
      return;
    }
    this.currentColor = color;
    // Immediately update selected strokes when color changes
    if (this.selectedStrokes.length > 0) {
      // Create color change operation
      const colorOp = {
        type: "colorChange",
        strokes: this.selectedStrokes.map((index) => {
          const stroke = this.drawingHistory[index];
          let oldColor;
          if (Array.isArray(stroke) && !stroke[0]?.type) {
            // For freehand strokes
            oldColor = stroke[0].color;
            stroke.forEach((point) => (point.color = color));
          } else if (stroke[0]?.type) {
            // For shapes
            oldColor = stroke[0].color;
            stroke[0].color = color;
          }
          return { index, oldColor };
        }),
      };

      // Add operation to history
      this.drawingHistory.push(colorOp);
      this.redoHistory = [];
      this.redrawCanvas();
      this.showStatus("Color updated for selection");
    }
  }

  setThickness(thickness) {
    if (this.readonly) {
      this.showStatus("Cannot change thickness in read-only mode");
      return;
    }
    this.currentThickness = parseInt(thickness);
    // Update thickness of selected strokes/shapes
    if (this.selectedStrokes.length > 0) {
      // Create thickness change operation
      const thicknessOp = {
        type: "thicknessChange",
        strokes: this.selectedStrokes.map((index) => ({
          index,
          oldThickness: this.drawingHistory[index][0].thickness,
          newThickness: thickness,
        })),
      };

      // Update thicknesses
      this.selectedStrokes.forEach((index) => {
        const stroke = this.drawingHistory[index];
        if (Array.isArray(stroke)) {
          stroke.forEach((point) => (point.thickness = thickness));
        } else if (stroke[0]?.type) {
          stroke[0].thickness = thickness;
        }
      });

      // Add operation to history
      this.drawingHistory.push(thicknessOp);
      this.redoHistory = [];
      this.redrawCanvas();
      this.showStatus("Thickness updated for selection");
    }
  }

  drawShape(shape, isPreview = false, isSelected = false) {
    const { ctx } = this;

    // Draw selection highlight background if selected
    if (isSelected) {
      ctx.save();
      ctx.strokeStyle = "#0066ff";
      // Cap the highlight thickness to a maximum of 4px more than the shape thickness
      const highlightThickness = Math.min(
        shape.thickness + 4,
        shape.thickness * 1.2,
      );
      ctx.lineWidth = highlightThickness;
      ctx.setLineDash([]);
      ctx.globalAlpha = 0.3;
      this.drawShapePath(shape);
      ctx.stroke();
      ctx.restore();
    }

    // Draw the main shape
    ctx.beginPath();
    ctx.strokeStyle = shape.color;
    ctx.fillStyle = shape.color;
    ctx.lineWidth = shape.thickness;

    // Save the current context state
    ctx.save();

    // If it's a preview, use dashed line and lighter color
    if (isPreview) {
      ctx.setLineDash([5, 5]);
      ctx.globalAlpha = shape.isFilled ? 0.3 : 0.6;
    }

    this.drawShapePath(shape);

    if (shape.isFilled) {
      ctx.fill();
    }
    ctx.stroke();

    // Draw white highlight for better visibility when selected
    if (isSelected) {
      ctx.strokeStyle = "#ffffff";
      // Cap the inner highlight thickness to a maximum of 2px more than the shape thickness
      const innerHighlightThickness = Math.min(
        shape.thickness + 2,
        shape.thickness * 1.1,
      );
      ctx.lineWidth = innerHighlightThickness;
      ctx.setLineDash([]);
      ctx.globalAlpha = 0.5;
      ctx.stroke();
    }

    // Restore the context state
    ctx.restore();
  }

  clear() {
    this.drawingHistory = [];
    this.redrawCanvas();
    console.log("Canvas cleared");
  }

  // Save current drawing state to JSON
  saveToJSON() {
    const saveData = {
      version: 1,
      timestamp: new Date().toISOString(),
      scale: this.scale,
      offsetX: this.offsetX,
      offsetY: this.offsetY,
      flipX: this.flipX,
      flipY: this.flipY,
      rotation: this.rotation,
      canvasWidth: this.canvas.width,
      canvasHeight: this.canvas.height,
      strokes: this.drawingHistory,
    };

    return JSON.stringify(saveData);
  }

  // Load drawing from JSON string
  loadFromJSON(jsonString) {
    try {
      const jsonData = JSON.parse(jsonString);

      // Check version compatibility
      if (jsonData.version !== 1) {
        throw new Error("Unsupported file version");
      }

      // Load the strokes
      this.drawingHistory = jsonData.strokes || [];

      // Load flip and rotation state
      this.flipX = jsonData.flipX || false;
      this.flipY = jsonData.flipY || false;
      this.rotation = jsonData.rotation || 0;

      // Check if we have canvas dimensions stored
      if (jsonData.canvasWidth && jsonData.canvasHeight) {
        // Calculate scale factors for width and height differences
        const widthRatio = this.canvas.width / jsonData.canvasWidth;
        const heightRatio = this.canvas.height / jsonData.canvasHeight;

        // Adjust offset to maintain relative position
        this.offsetX = jsonData.offsetX * widthRatio;
        this.offsetY = jsonData.offsetY * heightRatio;

        // Set the scale (using original scale or adjusted)
        this.scale = jsonData.scale || 1;

        this.showStatus("Drawing loaded with size adjustment");
      } else {
        // Use the saved values directly if no canvas dimensions were stored
        this.scale = jsonData.scale || 1;
        this.offsetX = jsonData.offsetX || 0;
        this.offsetY = jsonData.offsetY || 0;

        this.showStatus("Drawing loaded successfully");
      }

      // Apply pan limits to loaded state
      this.applyPanLimits();

      // Redraw
      this.redrawCanvas();

      return true;
    } catch (error) {
      this.showStatus("Error loading file: " + error.message);
      console.error("Error loading file:", error);
      return false;
    }
  }

  // Event binding
  bindEvents() {
    window.addEventListener("resize", () => this.resizeCanvas());
    this.container.addEventListener("wheel", (e) => this.onWheel(e));
    this.canvas.addEventListener("mousedown", (e) => this.onMouseDown(e));
    this.canvas.addEventListener("mousemove", (e) => this.onMouseMove(e));
    this.canvas.addEventListener("mouseup", () => this.onMouseUp());
    this.canvas.addEventListener("mouseleave", () => this.onMouseLeave());
    this.canvas.addEventListener("touchstart", (e) => this.onTouchStart(e));
    this.canvas.addEventListener("touchmove", (e) => this.onTouchMove(e));
    this.canvas.addEventListener("touchend", (e) => this.onTouchEnd(e));
    window.addEventListener("keydown", (e) => this.onKeyDown(e));
  }

  // Mouse wheel zooms around the pointer
  onWheel(e) {
    e.preventDefault();

    const mouseX = e.clientX;
    const mouseY = e.clientY;

    // Calculate position before zoom
    const pointBeforeZoomX = (mouseX - this.offsetX) / this.scale;
    const pointBeforeZoomY = (mouseY - this.offsetY) / this.scale;

    // Adjust zoom level
    const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
    this.scale *= zoomFactor;

    // Limit zoom
    this.scale = Math.min(Math.max(0.1, this.scale), 10);

    // Calculate position after zoom
    const pointAfterZoomX = (mouseX - this.offsetX) / this.scale;
    const pointAfterZoomY = (mouseY - this.offsetY) / this.scale;

    // Adjust offset to keep mouse position fixed
    this.offsetX += (pointAfterZoomX - pointBeforeZoomX) * this.scale;
    this.offsetY += (pointAfterZoomY - pointBeforeZoomY) * this.scale;

    this.applyPanLimits();
    this.redrawCanvas();
  }

  // Mouse: shift or middle-button drag pans (also in readonly mode); the left
  // button uses the current tool.
  onMouseDown(e) {
    if (e.shiftKey || e.button === 1) {
      this.startPan(e.clientX, e.clientY);
      this.canvas.style.cursor = "grabbing";
    } else if (!this.readonly) {
      const pos = this.getTransformedPosition(e.clientX, e.clientY);
      this.pointerDown(pos, e.ctrlKey || e.metaKey);
    }
  }

  onMouseMove(e) {
    if (this.isPanning) {
      this.panTo(e.clientX, e.clientY);
      return;
    }
    if (this.readonly) {
      return;
    }

    const pos = this.getTransformedPosition(e.clientX, e.clientY);

    // Show the resize cursor when hovering a selection handle
    if (
      this.currentTool === "select" &&
      !this.isSelecting &&
      !this.moveSelection.active &&
      !this.resizeHandles.active
    ) {
      const handle = this.getResizeHandleAtPoint(pos);
      this.canvas.style.cursor = handle ? handle.cursor : "default";
    }

    this.pointerMove(pos);
  }

  onMouseUp() {
    if (this.isPanning) {
      this.isPanning = false;
      this.canvas.style.cursor = "default";
      this.startX = null;
      this.startY = null;
    } else if (!this.readonly) {
      this.pointerUp();
    }
  }

  onMouseLeave() {
    if (this.isDrawing) {
      this.finishStroke();
      this.redrawCanvas();
    }
    if (this.isPanning) {
      this.isPanning = false;
      this.canvas.style.cursor = "default";
    }
  }

  // Touch: one finger uses the current tool; two fingers pan and pinch-zoom
  // (also in readonly mode).
  onTouchStart(e) {
    if (this.readonly && e.touches.length !== 2) {
      return;
    }
    e.preventDefault();

    const [first, second] = [e.touches[0], e.touches[1]];
    if (e.touches.length === 2) {
      this.startPan(
        (first.clientX + second.clientX) / 2,
        (first.clientY + second.clientY) / 2,
      );
      return;
    }

    this.pointerDown(this.getTransformedPosition(first.clientX, first.clientY));
  }

  onTouchMove(e) {
    if (this.readonly && e.touches.length !== 2) {
      return;
    }
    e.preventDefault();

    const [first, second] = [e.touches[0], e.touches[1]];
    if (e.touches.length === 2) {
      // Pinch-to-zoom: compare finger distance with the previous move
      const distance = Math.hypot(
        first.clientX - second.clientX,
        first.clientY - second.clientY,
      );
      if (e.target === this.canvas) {
        if (typeof this.lastDistance === "number") {
          const zoomFactor = distance > this.lastDistance ? 1.01 : 0.99;
          this.scale = Math.min(Math.max(0.1, this.scale * zoomFactor), 10);
        }
        this.lastDistance = distance;
      }

      this.panTo(
        (first.clientX + second.clientX) / 2,
        (first.clientY + second.clientY) / 2,
      );
      return;
    }

    this.pointerMove(this.getTransformedPosition(first.clientX, first.clientY));
  }

  onTouchEnd(e) {
    if (e.touches.length > 0) {
      return;
    }
    this.isPanning = false;
    this.lastDistance = null;
    // A gesture can begin with one finger and add a second; finish it either way
    if (!this.readonly) {
      this.pointerUp();
    }
  }

  startPan(clientX, clientY) {
    this.isPanning = true;
    this.startPanX = clientX - this.offsetX;
    this.startPanY = clientY - this.offsetY;
  }

  panTo(clientX, clientY) {
    this.offsetX = clientX - this.startPanX;
    this.offsetY = clientY - this.startPanY;
    this.applyPanLimits();
    this.redrawCanvas();
  }

  // Tool handling shared by mouse and touch. `additive` is Ctrl/Cmd: add to or
  // remove from the selection instead of replacing it.
  pointerDown(pos, additive = false) {
    this.startX = pos.x;
    this.startY = pos.y;

    if (this.currentTool === "select") {
      this.selectAt(pos, additive);
    } else if (this.currentTool === "pen") {
      this.isDrawing = true;
      this.currentStroke = [
        {
          x: pos.x,
          y: pos.y,
          color: this.currentColor,
          thickness: this.currentThickness,
        },
      ];
    }
  }

  pointerMove(pos) {
    if (this.resizeHandles.active) {
      this.resizeSelectedShapes(
        this.resizeHandles.activeHandle,
        pos.x - this.startX,
        pos.y - this.startY,
      );
      this.startX = pos.x;
      this.startY = pos.y;
      this.redrawCanvas();
    } else if (this.isDrawing && this.currentTool === "pen") {
      this.currentStroke.push({
        x: pos.x,
        y: pos.y,
        color: this.currentColor,
        thickness: this.currentThickness,
      });
      this.redrawCanvas();
    } else if (this.isSelecting) {
      this.selectionRect.width = pos.x - this.selectionRect.x;
      this.selectionRect.height = pos.y - this.selectionRect.y;
      this.redrawCanvas();
    } else if (this.moveSelection.active) {
      this.moveSelectedStrokes(
        pos.x - this.moveSelection.startX,
        pos.y - this.moveSelection.startY,
      );
      this.moveSelection.startX = pos.x;
      this.moveSelection.startY = pos.y;
      this.redrawCanvas();
    } else if (
      this.startX !== null &&
      this.currentTool !== "pen" &&
      this.currentTool !== "select"
    ) {
      this.previewShape = {
        type: this.currentTool,
        x: this.startX,
        y: this.startY,
        width: pos.x - this.startX,
        height: pos.y - this.startY,
        color: this.currentColor,
        thickness: this.currentThickness,
        isFilled: this.isFilled,
      };
      this.redrawCanvas();
    }
  }

  pointerUp() {
    if (this.resizeHandles.active) {
      this.resizeHandles.active = false;
      this.resizeHandles.activeHandle = null;
      this.canvas.style.cursor = "default";
    } else if (this.currentTool === "select") {
      this.finishSelection();
    } else if (this.currentTool === "pen" && this.isDrawing) {
      this.finishStroke();
    } else if (this.startX !== null && this.previewShape) {
      this.drawingHistory.push([this.previewShape]);
      this.redoHistory = [];
      this.previewShape = null;
      this.redrawCanvas();
    }

    this.startX = null;
    this.startY = null;
  }

  // Select tool press: grab a resize handle, start moving the selection, pick
  // the stroke under the pointer, or start a selection box.
  selectAt(pos, additive) {
    const handle = this.getResizeHandleAtPoint(pos);
    if (handle) {
      this.resizeHandles.active = true;
      this.resizeHandles.activeHandle = handle;
      this.canvas.style.cursor = handle.cursor;
      return;
    }

    if (
      this.selectedStrokes.length > 0 &&
      this.selectionRect &&
      this.isPointInRect(pos, this.selectionRect)
    ) {
      this.startMove(pos);
      return;
    }

    // Prefer already-selected strokes, then the topmost stroke
    let clickedIndex = this.selectedStrokes.find((index) =>
      this.isPointInStroke(pos, this.drawingHistory[index]),
    );
    if (clickedIndex === undefined) {
      clickedIndex = -1;
      for (let i = this.drawingHistory.length - 1; i >= 0; i--) {
        if (this.isPointInStroke(pos, this.drawingHistory[i])) {
          clickedIndex = i;
          break;
        }
      }
    }

    if (clickedIndex >= 0) {
      const wasSelected = this.selectedStrokes.includes(clickedIndex);
      if (!additive && !wasSelected) {
        this.selectedStrokes = [clickedIndex];
      } else if (additive && wasSelected) {
        this.selectedStrokes = this.selectedStrokes.filter(
          (i) => i !== clickedIndex,
        );
      } else if (additive) {
        this.selectedStrokes.push(clickedIndex);
      }

      if (this.selectedStrokes.includes(clickedIndex)) {
        this.startMove(pos);
      }
    } else if (!additive) {
      this.isSelecting = true;
      this.selectionRect = { x: pos.x, y: pos.y, width: 0, height: 0 };
      this.selectedStrokes = [];
    }

    this.redrawCanvas();
  }

  startMove(pos) {
    this.moveSelection.active = true;
    this.moveSelection.startX = pos.x;
    this.moveSelection.startY = pos.y;
    this.canvas.style.cursor = "move";
  }

  // Select tool release: apply the selection box, record a finished move, and
  // fit the selection rectangle to the selected strokes.
  finishSelection() {
    if (this.isSelecting && !this.moveSelection.active) {
      this.selectStrokesInRect(this.selectionRect);
    }

    // Record the move in history only once it is complete
    if (this.moveSelection.active && this.moveSelection.totalDx !== undefined) {
      this.drawingHistory.push({
        type: "move",
        strokes: [...this.selectedStrokes],
        dx: this.moveSelection.totalDx,
        dy: this.moveSelection.totalDy,
      });
      this.redoHistory = [];
    }

    this.isSelecting = false;
    this.moveSelection.active = false;
    this.moveSelection.totalDx = undefined;
    this.moveSelection.totalDy = undefined;
    this.canvas.style.cursor = "default";
    this.selectionRect = this.selectedStrokesBounds();
    this.redrawCanvas();
  }

  // Bounding box of the selected strokes and shapes, or null if none
  selectedStrokesBounds() {
    if (this.selectedStrokes.length === 0) {
      return null;
    }

    let minX = Infinity,
      minY = Infinity,
      maxX = -Infinity,
      maxY = -Infinity;
    this.selectedStrokes.forEach((index) => {
      const stroke = this.drawingHistory[index];
      if (Array.isArray(stroke) && !stroke[0]?.type) {
        // Freehand stroke
        stroke.forEach((point) => {
          minX = Math.min(minX, point.x);
          minY = Math.min(minY, point.y);
          maxX = Math.max(maxX, point.x);
          maxY = Math.max(maxY, point.y);
        });
      } else if (stroke[0]?.type) {
        // Shape
        const bounds = this.getShapeBounds(stroke[0]);
        minX = Math.min(minX, bounds.x);
        minY = Math.min(minY, bounds.y);
        maxX = Math.max(maxX, bounds.x + bounds.width);
        maxY = Math.max(maxY, bounds.y + bounds.height);
      }
    });

    return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
  }

  // End the pen stroke; a single point is a tap, not a stroke
  finishStroke() {
    this.isDrawing = false;
    if (this.currentStroke.length > 1) {
      this.drawingHistory.push(this.currentStroke);
      this.redoHistory = [];
    }
    this.currentStroke = [];
  }

  onKeyDown(e) {
    if (this.readonly) {
      return;
    }

    if (e.key === "Escape" && (this.previewShape || this.selectionRect)) {
      this.previewShape = null;
      this.selectionRect = null;
      this.isSelecting = false;
      this.startX = null;
      this.startY = null;
      this.selectedStrokes = [];
      this.redrawCanvas();
      this.showStatus("Operation cancelled");
      return;
    }

    if (e.ctrlKey || e.metaKey) {
      // Ctrl on Windows/Linux, Cmd on Mac
      const key = e.key.toLowerCase();
      const tool = {
        a: "select",
        p: "pen",
        r: "rectangle",
        l: "line",
        h: "hexagon",
      }[key];
      if (tool) {
        e.preventDefault();
        this.setTool(tool);
        return;
      }

      switch (key) {
        case "z":
          e.preventDefault();
          if (e.shiftKey) {
            this.redo();
          } else {
            this.undo();
          }
          break;
        case "y":
          e.preventDefault();
          this.redo();
          break;
        case "c":
          if (!e.shiftKey) {
            e.preventDefault();
            if (e.altKey) {
              this.setTool("circle");
            } else {
              this.copySelectedStrokes();
            }
          }
          break;
        case "x":
          e.preventDefault();
          this.cutSelectedStrokes();
          break;
        case "v":
          e.preventDefault();
          this.pasteStrokes();
          break;
        case "s":
          if (!e.shiftKey) {
            e.preventDefault();
            this.setTool("star");
          }
          break;
        case "f":
          e.preventDefault();
          this.setFill(!this.isFilled);
          break;
      }
    } else if (
      (e.key === "Backspace" || e.key === "Delete") &&
      this.selectedStrokes.length > 0
    ) {
      e.preventDefault();
      this.deleteSelectedStrokes();
    }
  }

  // Perfect freehand drawing helper methods
  getStrokePoints(points, options = {}) {
    if (!Array.isArray(points) || points.length < 2) {
      return points;
    }

    try {
      const { thinning = this.thinning, smoothing = this.smoothing } = options;

      const strokePoints = [];

      // Convert points to vectors for easier manipulation
      const vectors = points
        .filter((p) => p && typeof p === "object")
        .map((p, i) => {
          const next = points[i + 1];
          return next
            ? {
                x: next.x - p.x,
                y: next.y - p.y,
                pressure: p.pressure || 1,
                thickness: p.thickness,
                color: p.color,
              }
            : null;
        })
        .filter((v) => v);

      // Calculate control points for each segment
      for (let i = 0; i < points.length - 1; i++) {
        const p0 = points[i];
        const p1 = points[i + 1];

        if (!p0 || !p1) {
          continue;
        } // Skip invalid points

        // Calculate vector magnitude and direction
        const vector = vectors[i];
        if (!vector) {
          continue;
        }

        const magnitude = Math.sqrt(vector.x * vector.x + vector.y * vector.y);
        const angle = Math.atan2(vector.y, vector.x);

        // Calculate pressure based on velocity
        const velocity = Math.min(magnitude / 2, 4);
        const pressure = Math.max(0.1, 1 - velocity / 4);

        // Calculate control points for smoother curves
        const ctrl1 = {
          x: p0.x + Math.cos(angle) * magnitude * smoothing,
          y: p0.y + Math.sin(angle) * magnitude * smoothing,
        };

        const ctrl2 = {
          x: p1.x - Math.cos(angle) * magnitude * smoothing,
          y: p1.y - Math.sin(angle) * magnitude * smoothing,
        };

        // Add points with calculated properties
        strokePoints.push({
          x: p0.x,
          y: p0.y,
          ctrl1x: ctrl1.x,
          ctrl1y: ctrl1.y,
          ctrl2x: ctrl2.x,
          ctrl2y: ctrl2.y,
          pressure,
          thickness: p0.thickness * (1 - thinning * (1 - pressure)),
          color: p0.color,
        });
      }

      // Add the last point
      if (points.length > 0) {
        const last = points[points.length - 1];
        if (last) {
          strokePoints.push({
            x: last.x,
            y: last.y,
            pressure: 1,
            thickness: last.thickness,
            color: last.color,
          });
        }
      }

      return strokePoints;
    } catch (error) {
      console.warn("Error calculating stroke points:", error);
      return points;
    }
  }

  // LocalForage methods
  async autoSave() {
    try {
      await this.storage.setItem("lastSession", this.saveToJSON());
      this.showStatus("Auto-saved");
    } catch (error) {
      console.error("Auto-save failed:", error);
    }
  }

  // Selection methods
  isPointInStroke(point, stroke) {
    if (Array.isArray(stroke)) {
      // For freehand strokes
      for (let i = 0; i < stroke.length - 1; i++) {
        const p1 = stroke[i];
        const p2 = stroke[i + 1];
        const distance = this.pointToLineDistance(point, p1, p2);
        if (distance < 5) {
          return true;
        } // 5px tolerance
      }
      return false;
    } else if (stroke[0]?.type) {
      // For shapes
      const shape = stroke[0];
      const bounds = this.getShapeBounds(shape);
      return this.isPointInRect(point, bounds);
    }
    return false;
  }

  pointToLineDistance(point, lineStart, lineEnd) {
    const A = point.x - lineStart.x;
    const B = point.y - lineStart.y;
    const C = lineEnd.x - lineStart.x;
    const D = lineEnd.y - lineStart.y;

    const dot = A * C + B * D;
    const lenSq = C * C + D * D;
    let param = -1;

    if (lenSq !== 0) {
      param = dot / lenSq;
    }

    let xx, yy;

    if (param < 0) {
      xx = lineStart.x;
      yy = lineStart.y;
    } else if (param > 1) {
      xx = lineEnd.x;
      yy = lineEnd.y;
    } else {
      xx = lineStart.x + param * C;
      yy = lineStart.y + param * D;
    }

    const dx = point.x - xx;
    const dy = point.y - yy;

    return Math.sqrt(dx * dx + dy * dy);
  }

  getShapeBounds(shape) {
    return {
      x: Math.min(shape.x, shape.x + shape.width),
      y: Math.min(shape.y, shape.y + shape.height),
      width: Math.abs(shape.width),
      height: Math.abs(shape.height),
    };
  }

  isPointInRect(point, rect) {
    return (
      point.x >= rect.x &&
      point.x <= rect.x + rect.width &&
      point.y >= rect.y &&
      point.y <= rect.y + rect.height
    );
  }

  selectStrokesInRect(rect) {
    const normalizedRect = {
      x: Math.min(rect.x, rect.x + rect.width),
      y: Math.min(rect.y, rect.y + rect.height),
      width: Math.abs(rect.width),
      height: Math.abs(rect.height),
    };

    this.selectedStrokes = [];

    // Keep track of newly selected strokes
    const newlySelected = [];

    this.drawingHistory.forEach((stroke, index) => {
      if (Array.isArray(stroke) && !stroke[0]?.type) {
        // For freehand strokes
        for (const point of stroke) {
          if (this.isPointInRect(point, normalizedRect)) {
            if (!this.selectedStrokes.includes(index)) {
              newlySelected.push(index);
            }
            break;
          }
        }
      } else if (stroke[0]?.type) {
        // For shapes
        const shapeBounds = this.getShapeBounds(stroke[0]);
        if (
          this.rectsIntersect(normalizedRect, shapeBounds) &&
          !this.selectedStrokes.includes(index)
        ) {
          newlySelected.push(index);
        }
      }
    });

    // Add newly selected strokes to selection
    this.selectedStrokes.push(...newlySelected);

    // Update UI controls based on the last selected stroke
    if (this.selectedStrokes.length > 0) {
      const lastSelectedStroke =
        this.drawingHistory[
          this.selectedStrokes[this.selectedStrokes.length - 1]
        ];
      if (Array.isArray(lastSelectedStroke) && !lastSelectedStroke[0]?.type) {
        // For freehand strokes
        const color = lastSelectedStroke[0]?.color;
        const thickness = lastSelectedStroke[0]?.thickness;
        this.updateUIControls(color, thickness);
      } else if (lastSelectedStroke[0]?.type) {
        // For shapes
        const color = lastSelectedStroke[0]?.color;
        const thickness = lastSelectedStroke[0]?.thickness;
        this.updateUIControls(color, thickness);
      }
    }

    this.redrawCanvas();
  }

  // Add new method to update UI controls
  updateUIControls(color, thickness) {
    if (this.externalUpdateUIControls) {
      this.externalUpdateUIControls(color, thickness);
    } else {
      // Fallback implementation
      if (color) {
        const colorPicker = document.getElementById("pathColorPicker");
        if (colorPicker) {
          colorPicker.value = color;
          // Update Coloris field and button
          const clrField = colorPicker.closest(".clr-field");
          if (clrField) {
            clrField.style.color = color;
            const button = clrField.querySelector("button");
            if (button) {
              button.style.backgroundColor = color;
            }
          }
        }
      }
      if (thickness) {
        const thicknessSlider = document.getElementById("pathThickness");
        const thicknessDisplay = document.getElementById("pathThicknessValue");
        if (thicknessSlider) {
          thicknessSlider.value = thickness;
          if (thicknessDisplay) {
            thicknessDisplay.textContent = thickness;
          }
        }
      }
    }
  }

  rectsIntersect(rect1, rect2) {
    return !(
      rect2.x > rect1.x + rect1.width ||
      rect2.x + rect2.width < rect1.x ||
      rect2.y > rect1.y + rect1.height ||
      rect2.y + rect2.height < rect1.y
    );
  }

  moveSelectedStrokes(dx, dy) {
    if (dx === 0 && dy === 0) {
      return;
    }

    // Just move the strokes without recording history during dragging
    for (const index of this.selectedStrokes) {
      const stroke = this.drawingHistory[index];
      if (Array.isArray(stroke)) {
        // Move freehand stroke
        stroke.forEach((point) => {
          point.x += dx;
          point.y += dy;
        });
      } else if (stroke[0]?.type) {
        // Move shape
        stroke[0].x += dx;
        stroke[0].y += dy;
      }
    }

    // Move the selection rectangle along with the strokes
    if (this.selectionRect) {
      this.selectionRect.x += dx;
      this.selectionRect.y += dy;
    }

    // Accumulate total movement
    if (!this.moveSelection.totalDx) {
      this.moveSelection.totalDx = 0;
    }
    if (!this.moveSelection.totalDy) {
      this.moveSelection.totalDy = 0;
    }
    this.moveSelection.totalDx += dx;
    this.moveSelection.totalDy += dy;
  }

  copySelectedStrokes() {
    this.selectedStrokesCopy = this.selectedStrokes.map((index) => {
      const stroke = this.drawingHistory[index];
      if (Array.isArray(stroke)) {
        // Deep copy freehand stroke
        return stroke.map((point) => ({ ...point }));
      } else if (stroke[0]?.type) {
        // Deep copy shape
        return [{ ...stroke[0] }];
      }
    });
    this.showStatus("Selection copied");
  }

  cutSelectedStrokes() {
    this.copySelectedStrokes();
    this.deleteSelectedStrokes();
    this.showStatus("Selection cut");
  }

  pasteStrokes() {
    if (!this.selectedStrokesCopy) {
      this.showStatus("Nothing to paste");
      return;
    }

    // Create paste operation
    const pasteOp = {
      type: "paste",
      newStrokes: [],
    };

    // Add offset to avoid exact overlap
    const offset = 20;
    this.selectedStrokes = [];

    this.selectedStrokesCopy.forEach((stroke) => {
      if (Array.isArray(stroke)) {
        // Paste freehand stroke with offset
        const newStroke = stroke.map((point) => ({
          ...point,
          x: point.x + offset,
          y: point.y + offset,
        }));
        this.drawingHistory.push(newStroke);
        const newIndex = this.drawingHistory.length - 1;
        this.selectedStrokes.push(newIndex);
        pasteOp.newStrokes.push({ index: newIndex, stroke: newStroke });
      } else if (stroke[0]?.type) {
        // Paste shape with offset
        const newShape = [
          {
            ...stroke[0],
            x: stroke[0].x + offset,
            y: stroke[0].y + offset,
          },
        ];
        this.drawingHistory.push(newShape);
        const newIndex = this.drawingHistory.length - 1;
        this.selectedStrokes.push(newIndex);
        pasteOp.newStrokes.push({ index: newIndex, stroke: newShape });
      }
    });

    // Add paste operation to history
    this.drawingHistory.push(pasteOp);
    this.redoHistory = [];
    this.redrawCanvas();
    this.showStatus("Selection pasted");
  }

  deleteSelectedStrokes() {
    if (this.selectedStrokes.length === 0) {
      return;
    }

    // Create delete operation
    const deleteOp = {
      type: "delete",
      strokes: this.selectedStrokes.map((index) => ({
        index,
        stroke: this.drawingHistory[index],
      })),
    };

    // Sort indices in descending order to avoid shifting issues
    const sortedIndices = [...this.selectedStrokes].sort((a, b) => b - a);
    sortedIndices.forEach((index) => {
      this.drawingHistory.splice(index, 1);
    });

    // Add delete operation to history
    this.drawingHistory.push(deleteOp);

    // Clear selection and selection rectangle
    this.selectedStrokes = [];
    this.selectionRect = null;

    this.redoHistory = [];
    this.redrawCanvas();
    this.showStatus("Selection deleted");
  }

  // Clean up method
  destroy() {
    clearInterval(this.autoSaveInterval);
  }

  // Helper method to draw a regular polygon
  drawPolygon(ctx, x, y, radius, sides, startAngle = 0) {
    ctx.beginPath();
    for (let i = 0; i < sides; i++) {
      const angle = startAngle + (i * 2 * Math.PI) / sides;
      const pointX = x + radius * Math.cos(angle);
      const pointY = y + radius * Math.sin(angle);
      if (i === 0) {
        ctx.moveTo(pointX, pointY);
      } else {
        ctx.lineTo(pointX, pointY);
      }
    }
    ctx.closePath();
  }

  // Helper method to draw a star
  drawStar(ctx, x, y, radius, points = 5, innerRadius = null) {
    if (innerRadius === null) {
      innerRadius = radius / 2;
    }

    ctx.beginPath();
    for (let i = 0; i < points * 2; i++) {
      const angle = (i * Math.PI) / points;
      const r = i % 2 === 0 ? radius : innerRadius;
      const pointX = x + r * Math.cos(angle - Math.PI / 2);
      const pointY = y + r * Math.sin(angle - Math.PI / 2);
      if (i === 0) {
        ctx.moveTo(pointX, pointY);
      } else {
        ctx.lineTo(pointX, pointY);
      }
    }
    ctx.closePath();
  }

  // Helper method to draw shape paths
  drawShapePath(shape) {
    const width = Math.abs(shape.width);
    const height = Math.abs(shape.height);
    const centerX = shape.x + shape.width / 2;
    const centerY = shape.y + shape.height / 2;
    const radius =
      Math.sqrt(shape.width * shape.width + shape.height * shape.height) / 2;

    this.ctx.beginPath();
    switch (shape.type) {
      case "rectangle":
        this.ctx.rect(shape.x, shape.y, shape.width, shape.height);
        break;
      case "circle":
        this.ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        break;
      case "line":
        this.ctx.moveTo(shape.x, shape.y);
        this.ctx.lineTo(shape.x + shape.width, shape.y + shape.height);
        break;
      case "arrow":
        // Draw the main line
        this.ctx.moveTo(shape.x, shape.y);
        this.ctx.lineTo(shape.x + shape.width, shape.y + shape.height);

        // Draw the arrowhead
        const angle = Math.atan2(shape.height, shape.width);
        const arrowLength = Math.min(
          20,
          Math.sqrt(width * width + height * height) / 3,
        );
        const arrowAngle = Math.PI / 6; // 30 degrees

        // Calculate arrowhead points
        const x2 = shape.x + shape.width;
        const y2 = shape.y + shape.height;

        // Draw the two lines of the arrowhead
        this.ctx.moveTo(x2, y2);
        this.ctx.lineTo(
          x2 - arrowLength * Math.cos(angle - arrowAngle),
          y2 - arrowLength * Math.sin(angle - arrowAngle),
        );
        this.ctx.moveTo(x2, y2);
        this.ctx.lineTo(
          x2 - arrowLength * Math.cos(angle + arrowAngle),
          y2 - arrowLength * Math.sin(angle + arrowAngle),
        );
        break;
      case "hexagon":
        this.drawPolygon(this.ctx, centerX, centerY, radius, 6, Math.PI / 6);
        break;
      case "star":
        this.drawStar(this.ctx, centerX, centerY, radius);
        break;
    }
  }

  // Add method to draw resize handles
  drawResizeHandles() {
    if (!this.selectionRect || this.selectedStrokes.length === 0) {
      return;
    }

    const handles = [
      {
        x: this.selectionRect.x,
        y: this.selectionRect.y,
        cursor: "nw-resize",
        position: "nw",
      },
      {
        x: this.selectionRect.x + this.selectionRect.width,
        y: this.selectionRect.y,
        cursor: "ne-resize",
        position: "ne",
      },
      {
        x: this.selectionRect.x + this.selectionRect.width,
        y: this.selectionRect.y + this.selectionRect.height,
        cursor: "se-resize",
        position: "se",
      },
      {
        x: this.selectionRect.x,
        y: this.selectionRect.y + this.selectionRect.height,
        cursor: "sw-resize",
        position: "sw",
      },
    ];

    this.resizeHandles.positions = handles;

    // Draw handles
    this.ctx.save();
    this.ctx.fillStyle = "#ffffff";
    this.ctx.strokeStyle = "#0066ff";
    this.ctx.lineWidth = 2;

    handles.forEach((handle) => {
      this.ctx.beginPath();
      this.ctx.rect(
        handle.x - this.resizeHandles.size / 2,
        handle.y - this.resizeHandles.size / 2,
        this.resizeHandles.size,
        this.resizeHandles.size,
      );
      this.ctx.fill();
      this.ctx.stroke();
    });

    this.ctx.restore();
  }

  // Add method to check if a point is inside a resize handle
  getResizeHandleAtPoint(point) {
    if (!this.resizeHandles.positions.length) {
      return null;
    }

    for (const handle of this.resizeHandles.positions) {
      const handleBounds = {
        x: handle.x - this.resizeHandles.size / 2,
        y: handle.y - this.resizeHandles.size / 2,
        width: this.resizeHandles.size,
        height: this.resizeHandles.size,
      };

      if (this.isPointInRect(point, handleBounds)) {
        return handle;
      }
    }
    return null;
  }

  // Add method to resize selected shapes
  resizeSelectedShapes(handle, dx, dy) {
    if (!this.selectionRect || this.selectedStrokes.length === 0) {
      return;
    }

    const originalRect = { ...this.selectionRect };
    let scaleX = 1,
      scaleY = 1;
    let translateX = 0,
      translateY = 0;

    // Calculate scale factors based on which handle is being dragged
    switch (handle.position) {
      case "nw":
        scaleX = (originalRect.width - dx) / originalRect.width;
        scaleY = (originalRect.height - dy) / originalRect.height;
        translateX = dx;
        translateY = dy;
        this.selectionRect.x += dx;
        this.selectionRect.y += dy;
        this.selectionRect.width -= dx;
        this.selectionRect.height -= dy;
        break;
      case "ne":
        scaleX = (originalRect.width + dx) / originalRect.width;
        scaleY = (originalRect.height - dy) / originalRect.height;
        translateY = dy;
        this.selectionRect.y += dy;
        this.selectionRect.width += dx;
        this.selectionRect.height -= dy;
        break;
      case "se":
        scaleX = (originalRect.width + dx) / originalRect.width;
        scaleY = (originalRect.height + dy) / originalRect.height;
        this.selectionRect.width += dx;
        this.selectionRect.height += dy;
        break;
      case "sw":
        scaleX = (originalRect.width - dx) / originalRect.width;
        scaleY = (originalRect.height + dy) / originalRect.height;
        translateX = dx;
        this.selectionRect.x += dx;
        this.selectionRect.width -= dx;
        this.selectionRect.height += dy;
        break;
    }

    // Update all selected shapes
    this.selectedStrokes.forEach((index) => {
      const stroke = this.drawingHistory[index];
      if (Array.isArray(stroke) && !stroke[0]?.type) {
        // For freehand strokes
        stroke.forEach((point) => {
          // Calculate point position relative to selection rect
          const relX = (point.x - originalRect.x) / originalRect.width;
          const relY = (point.y - originalRect.y) / originalRect.height;

          // Apply scaling and translation
          point.x =
            originalRect.x + translateX + relX * originalRect.width * scaleX;
          point.y =
            originalRect.y + translateY + relY * originalRect.height * scaleY;
        });
      } else if (stroke[0]?.type) {
        // For shapes
        const shape = stroke[0];
        // Calculate shape position relative to selection rect
        const relX = (shape.x - originalRect.x) / originalRect.width;
        const relY = (shape.y - originalRect.y) / originalRect.height;

        // Apply scaling and translation
        shape.x =
          originalRect.x + translateX + relX * originalRect.width * scaleX;
        shape.y =
          originalRect.y + translateY + relY * originalRect.height * scaleY;
        shape.width *= scaleX;
        shape.height *= scaleY;
      }
    });

    // Update handle positions
    this.updateResizeHandles();
  }

  updateResizeHandles() {
    if (!this.selectionRect) {
      return;
    }

    const rect = this.selectionRect;
    const handleSize = this.resizeHandles.size;

    this.resizeHandles.positions = [
      {
        x: rect.x - handleSize / 2,
        y: rect.y - handleSize / 2,
        position: "nw",
        cursor: "nw-resize",
      },
      {
        x: rect.x + rect.width / 2 - handleSize / 2,
        y: rect.y - handleSize / 2,
        position: "n",
        cursor: "n-resize",
      },
      {
        x: rect.x + rect.width - handleSize / 2,
        y: rect.y - handleSize / 2,
        position: "ne",
        cursor: "ne-resize",
      },
      {
        x: rect.x - handleSize / 2,
        y: rect.y + rect.height / 2 - handleSize / 2,
        position: "w",
        cursor: "w-resize",
      },
      {
        x: rect.x + rect.width - handleSize / 2,
        y: rect.y + rect.height / 2 - handleSize / 2,
        position: "e",
        cursor: "e-resize",
      },
      {
        x: rect.x - handleSize / 2,
        y: rect.y + rect.height - handleSize / 2,
        position: "sw",
        cursor: "sw-resize",
      },
      {
        x: rect.x + rect.width / 2 - handleSize / 2,
        y: rect.y + rect.height - handleSize / 2,
        position: "s",
        cursor: "s-resize",
      },
      {
        x: rect.x + rect.width - handleSize / 2,
        y: rect.y + rect.height - handleSize / 2,
        position: "se",
        cursor: "se-resize",
      },
    ];
  }

  // Add method to toggle readonly mode
  setReadonly(readonly) {
    this.readonly = readonly;
    clearInterval(this.autoSaveInterval);
    this.autoSaveInterval = readonly ? null : setInterval(() => this.autoSave(), 30000);
    if (readonly) {
      // Clear any ongoing operations
      this.isDrawing = false;
      this.isPanning = false;
      this.isSelecting = false;
      this.moveSelection.active = false;
      this.resizeHandles.active = false;
      this.selectedStrokes = [];
      this.selectionRect = null;
      this.currentStroke = [];
      this.previewShape = null;
      this.canvas.style.cursor = "default";
      this.redrawCanvas();
      console.log("Read-only mode enabled");
    } else {
      console.log("Edit mode enabled");
    }
  }

  // Flip canvas horizontally
  flipHorizontal() {
    this.flipX = !this.flipX;
    this.redrawCanvas();
    this.showStatus(
      this.flipX ? "Canvas flipped horizontally" : "Horizontal flip removed",
    );
  }

  // Flip canvas vertically
  flipVertical() {
    this.flipY = !this.flipY;
    this.redrawCanvas();
    this.showStatus(
      this.flipY ? "Canvas flipped vertically" : "Vertical flip removed",
    );
  }

  // Rotate canvas clockwise by 90 degrees
  rotateClockwise() {
    this.rotation = (this.rotation + 90) % 360;
    this.redrawCanvas();
    this.showStatus(`Canvas rotated to ${this.rotation}°`);
  }

  // Rotate canvas counter-clockwise by 90 degrees
  rotateCounterClockwise() {
    this.rotation = (this.rotation - 90 + 360) % 360;
    this.redrawCanvas();
    this.showStatus(`Canvas rotated to ${this.rotation}°`);
  }

  // Reset all transformations (flip and rotation)
  resetTransformations() {
    this.flipX = false;
    this.flipY = false;
    this.rotation = 0;
    this.redrawCanvas();
    this.showStatus("All transformations reset");
  }
}
