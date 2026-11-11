const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const SOURCE = fs.readFileSync('app/static/js/Canvas.js', 'utf8');
const BOUNDS = {left: 0, top: 0, width: 800, height: 400};

// Canvas.js in a fake browser: an 800x400 canvas whose 2D context accepts any call.
function whiteboard(options = {}) {
  const listeners = new Map();
  const on = target => (name, handler) => listeners.set(`${target}:${name}`, handler);
  const ctx = new Proxy({}, {get: (props, key) => key in props ? props[key] : () => {}});
  const canvas = {width: 0, height: 0, style: {}, getContext: () => ctx,
    addEventListener: on('canvas'), getBoundingClientRect: () => BOUNDS};
  const container = {addEventListener: on('container'), getBoundingClientRect: () => BOUNDS};
  const statuses = [];
  const Canvas = vm.runInNewContext(`${SOURCE}\nCanvas;`, {
    window: {devicePixelRatio: 1, addEventListener: on('window')},
    document: {getElementById: () => null, createElement: () => ({getContext: () => ctx})},
    matchMedia: () => ({addEventListener() {}}),
    localforage: {createInstance: () => ({setItem: async () => {}})},
    Image: class {}, setInterval: () => 0, clearInterval() {}, setTimeout() {},
    console: {log() {}, warn() {}, error() {}},
  });
  const board = new Canvas({canvas, container, showStatus: message => statuses.push(message), ...options});
  // Identity view so client coordinates equal drawing coordinates.
  Object.assign(board, {scale: 1, offsetX: 0, offsetY: 0});
  const fire = (key, event) => listeners.get(key)({preventDefault() {}, ...event});
  return {board, canvas, statuses, fire};
}

const mouseEvent = (x, y, mods = {}) => ({clientX: x, clientY: y, button: 0, ...mods});
const touchEvent = (page, points) => ({target: page.canvas,
  touches: points.map(([x, y]) => ({clientX: x, clientY: y}))});

// Single-pointer input through each device's events; touch has no modifier keys.
const devices = {
  mouse: page => ({
    down: (x, y, mods) => page.fire('canvas:mousedown', mouseEvent(x, y, mods)),
    move: (x, y) => page.fire('canvas:mousemove', mouseEvent(x, y)),
    up: (x, y) => page.fire('canvas:mouseup', mouseEvent(x, y)),
  }),
  touch: page => ({
    down: (x, y) => page.fire('canvas:touchstart', touchEvent(page, [[x, y]])),
    move: (x, y) => page.fire('canvas:touchmove', touchEvent(page, [[x, y]])),
    up: () => page.fire('canvas:touchend', touchEvent(page, [])),
  }),
};

function drag(input, ...points) {
  input.down(...points[0]);
  points.slice(1).forEach(point => input.move(...point));
  input.up(...points.at(-1));
}

function click(input, x, y, mods) {
  input.down(x, y, mods);
  input.up(x, y);
}

// Values from the sandbox realm compare by prototype; copy them into this realm.
const plain = value => JSON.parse(JSON.stringify(value));
const xy = stroke => Array.from(stroke, ({x, y}) => [x, y]);
const key = (page, k, mods = {}) => page.fire('window:keydown', {key: k, ...mods});

for (const [device, connect] of Object.entries(devices)) {
  test(`${device}: pen drag records one stroke with colour and thickness`, () => {
    const page = whiteboard({initialColor: '#ff0000', initialThickness: 5});
    drag(connect(page), [10, 10], [20, 10], [30, 15]);
    assert.equal(page.board.drawingHistory.length, 1);
    const stroke = page.board.drawingHistory[0];
    assert.deepEqual(xy(stroke), [[10, 10], [20, 10], [30, 15]]);
    assert.ok(stroke.every(p => p.color === '#ff0000' && p.thickness === 5));
    assert.equal(page.board.currentStroke.length, 0);
    assert.equal(page.board.isDrawing, false);
  });

  test(`${device}: a pen tap without movement records nothing`, () => {
    const page = whiteboard();
    drag(connect(page), [10, 10]);
    assert.equal(page.board.drawingHistory.length, 0);
  });

  test(`${device}: shape drag records the shape and clears the preview`, () => {
    const page = whiteboard();
    page.board.setTool('rectangle');
    page.board.setFill(true);
    drag(connect(page), [10, 10], [30, 20], [50, 40]);
    assert.equal(page.board.drawingHistory.length, 1);
    const [shape] = page.board.drawingHistory[0];
    assert.deepEqual(plain(shape), {type: 'rectangle', x: 10, y: 10, width: 40, height: 30,
      color: '#000000', thickness: 3, isFilled: true});
    assert.equal(page.board.previewShape, null);
    assert.equal(page.board.startX, null);
  });

  test(`${device}: a shape tap without movement records nothing`, () => {
    const page = whiteboard();
    page.board.setTool('circle');
    drag(connect(page), [10, 10]);
    assert.equal(page.board.drawingHistory.length, 0);
  });

  test(`${device}: drawing after undo discards the redo history`, () => {
    const page = whiteboard();
    const input = connect(page);
    drag(input, [10, 10], [20, 20]);
    page.board.undo();
    assert.equal(page.board.redoHistory.length, 1);
    drag(input, [50, 50], [60, 60]);
    assert.equal(page.board.redoHistory.length, 0);
    page.board.setTool('line');
    drag(input, [0, 0], [5, 5]);
    page.board.undo();
    drag(input, [0, 0], [9, 9]);
    assert.equal(page.board.redoHistory.length, 0);
  });

  test(`${device}: dragging a stroke moves it and undo/redo replay the move`, () => {
    const page = whiteboard();
    const input = connect(page);
    drag(input, [10, 10], [50, 10]);
    page.board.setTool('select');
    drag(input, [30, 10], [35, 15], [40, 20]);
    assert.deepEqual(plain(page.board.selectedStrokes), [0]);
    assert.deepEqual(xy(page.board.drawingHistory[0]), [[20, 20], [60, 20]]);
    assert.deepEqual(plain(page.board.drawingHistory[1]), {type: 'move', strokes: [0], dx: 10, dy: 10});
    assert.deepEqual(plain(page.board.selectionRect), {x: 20, y: 20, width: 40, height: 0});
    assert.equal(page.board.moveSelection.active, false);
    page.board.undo();
    assert.deepEqual(xy(page.board.drawingHistory[0]), [[10, 10], [50, 10]]);
    page.board.redo();
    assert.deepEqual(xy(page.board.drawingHistory[0]), [[20, 20], [60, 20]]);
  });

  test(`${device}: dragging inside the selection moves every selected stroke`, () => {
    const page = whiteboard();
    const input = connect(page);
    drag(input, [10, 10], [20, 10]);
    drag(input, [10, 30], [20, 30]);
    page.board.setTool('select');
    drag(input, [0, 0], [100, 100]);
    assert.deepEqual(plain(page.board.selectedStrokes), [0, 1]);
    drag(input, [15, 20], [25, 20]);
    assert.deepEqual(plain(page.board.selectedStrokes), [0, 1]);
    assert.deepEqual(xy(page.board.drawingHistory[0]), [[20, 10], [30, 10]]);
    assert.deepEqual(xy(page.board.drawingHistory[1]), [[20, 30], [30, 30]]);
  });

  test(`${device}: box select picks touching strokes and shapes, empty box clears`, () => {
    const page = whiteboard();
    const input = connect(page);
    drag(input, [10, 10], [20, 10]);
    page.board.setTool('rectangle');
    drag(input, [100, 100], [140, 130]);
    drag(input, [300, 300], [310, 310]);
    page.board.setTool('select');
    drag(input, [0, 0], [120, 120]);
    assert.deepEqual(plain(page.board.selectedStrokes), [0, 1]);
    assert.deepEqual(plain(page.board.selectionRect), {x: 10, y: 10, width: 130, height: 120});
    assert.equal(page.board.isSelecting, false);
    drag(input, [500, 20], [600, 60]);
    assert.deepEqual(plain(page.board.selectedStrokes), []);
    assert.equal(page.board.selectionRect, null);
  });

  test(`${device}: dragging a corner handle resizes the selected shape`, () => {
    const page = whiteboard();
    const input = connect(page);
    page.board.setTool('rectangle');
    drag(input, [10, 10], [50, 40]);
    page.board.setTool('select');
    drag(input, [0, 0], [60, 60]);
    // Bottom-right handle covers (42..50, 32..40)
    drag(input, [47, 37], [52, 42], [57, 47]);
    const [shape] = page.board.drawingHistory[0];
    assert.deepEqual([shape.x, shape.y, shape.width, shape.height], [10, 10, 50, 40]);
    assert.deepEqual(plain(page.board.selectionRect), {x: 10, y: 10, width: 50, height: 40});
    assert.equal(page.board.resizeHandles.active, false);
  });

  test(`${device}: read-only boards ignore single-pointer drawing and selection`, () => {
    const page = whiteboard();
    const input = connect(page);
    page.board.setReadonly(true);
    drag(input, [10, 10], [50, 50]);
    page.board.currentTool = 'select';
    drag(input, [0, 0], [60, 60]);
    assert.equal(page.board.drawingHistory.length, 0);
    assert.equal(page.board.selectionRect, null);
    assert.equal(page.board.isPanning, false);
  });
}

test('mouse: Ctrl/Cmd click adds and removes strokes from the selection', () => {
  const page = whiteboard();
  const input = devices.mouse(page);
  drag(input, [10, 10], [20, 10]);
  drag(input, [10, 30], [20, 30]);
  page.board.setTool('select');
  drag(input, [15, 10]);
  click(input, 15, 30, {ctrlKey: true});
  assert.deepEqual(plain(page.board.selectedStrokes), [0, 1]);
  page.board.selectionRect = null;
  click(input, 15, 10, {metaKey: true});
  assert.deepEqual(plain(page.board.selectedStrokes), [1]);
  page.board.selectionRect = null;
  click(input, 300, 300, {ctrlKey: true});
  assert.deepEqual(plain(page.board.selectedStrokes), [1]);
});

test('mouse: clicking a stroke selects only it', () => {
  const page = whiteboard();
  const input = devices.mouse(page);
  drag(input, [10, 10], [20, 10]);
  drag(input, [10, 30], [20, 30]);
  page.board.setTool('select');
  drag(input, [15, 10]);
  page.board.selectionRect = null;
  drag(input, [15, 30]);
  assert.deepEqual(plain(page.board.selectedStrokes), [1]);
});

test('mouse: cursor follows panning, moving, and resize handles', () => {
  const page = whiteboard();
  const input = devices.mouse(page);
  page.board.setTool('rectangle');
  drag(input, [10, 10], [50, 40]);
  page.board.setTool('select');
  drag(input, [0, 0], [60, 60]);
  input.move(47, 37);
  assert.equal(page.canvas.style.cursor, 'se-resize');
  input.move(30, 20);
  assert.equal(page.canvas.style.cursor, 'default');
  input.down(30, 20);
  assert.equal(page.canvas.style.cursor, 'move');
  input.up(30, 20);
  assert.equal(page.canvas.style.cursor, 'default');
  input.down(30, 20, {shiftKey: true});
  assert.equal(page.canvas.style.cursor, 'grabbing');
  input.up(30, 20);
  assert.equal(page.canvas.style.cursor, 'default');
});

test('mouse: shift or middle-button drag pans, including on read-only boards', () => {
  for (const [mods, readonly] of [[{shiftKey: true}, false], [{button: 1}, false], [{shiftKey: true}, true]]) {
    const page = whiteboard();
    const input = devices.mouse(page);
    page.board.setReadonly(readonly);
    Object.assign(page.board, {offsetX: 400, offsetY: 200});
    input.down(100, 100, mods);
    input.move(130, 90);
    assert.deepEqual([page.board.offsetX, page.board.offsetY], [430, 190]);
    input.up(130, 90);
    assert.equal(page.board.isPanning, false);
    assert.equal(page.board.drawingHistory.length, 0);
  }
});

test('mouse: leaving the canvas mid-stroke keeps the stroke and stops panning', () => {
  const page = whiteboard();
  const input = devices.mouse(page);
  drag(input, [0, 0], [5, 5]);
  page.board.undo();
  input.down(10, 10);
  input.move(20, 20);
  page.fire('canvas:mouseleave', {});
  assert.equal(page.board.drawingHistory.length, 1);
  assert.equal(page.board.redoHistory.length, 0);
  assert.equal(page.board.isDrawing, false);
  input.down(10, 10, {shiftKey: true});
  page.fire('canvas:mouseleave', {});
  assert.equal(page.board.isPanning, false);
});

test('mouse: wheel zooms around the pointer within limits', () => {
  const page = whiteboard();
  Object.assign(page.board, {offsetX: 400, offsetY: 200});
  page.fire('container:wheel', {clientX: 400, clientY: 200, deltaY: -1});
  assert.ok(Math.abs(page.board.scale - 1.1) < 1e-9);
  assert.deepEqual([page.board.offsetX, page.board.offsetY], [400, 200]);
  for (let i = 0; i < 100; i++) page.fire('container:wheel', {clientX: 400, clientY: 200, deltaY: 1});
  assert.equal(page.board.scale, 0.1);
});

test('touch: two fingers pan and pinch, including on read-only boards', () => {
  for (const readonly of [false, true]) {
    const page = whiteboard();
    page.board.setReadonly(readonly);
    Object.assign(page.board, {offsetX: 400, offsetY: 200});
    page.fire('canvas:touchstart', touchEvent(page, [[100, 100], [200, 100]]));
    page.fire('canvas:touchmove', touchEvent(page, [[110, 90], [210, 90]]));
    assert.deepEqual([page.board.offsetX, page.board.offsetY], [410, 190]);
    assert.equal(page.board.scale, 1);
    page.fire('canvas:touchmove', touchEvent(page, [[90, 90], [230, 90]]));
    assert.equal(page.board.scale, 1.01);
    page.fire('canvas:touchend', touchEvent(page, []));
    assert.equal(page.board.isPanning, false);
    assert.equal(page.board.lastDistance, null);
    assert.equal(page.board.drawingHistory.length, 0);
  }
});

test('keyboard shortcuts edit, select tools, and stay off in read-only mode', () => {
  const page = whiteboard();
  const input = devices.mouse(page);
  drag(input, [10, 10], [20, 10]);
  key(page, 'z', {ctrlKey: true});
  assert.equal(page.board.drawingHistory.length, 0);
  key(page, 'Z', {ctrlKey: true, shiftKey: true});
  assert.equal(page.board.drawingHistory.length, 1);
  key(page, 'z', {metaKey: true});
  key(page, 'y', {ctrlKey: true});
  assert.equal(page.board.drawingHistory.length, 1);

  for (const [k, mods, tool] of [['a', {}, 'select'], ['p', {}, 'pen'], ['r', {}, 'rectangle'],
    ['c', {altKey: true}, 'circle'], ['l', {}, 'line'], ['h', {}, 'hexagon'], ['s', {}, 'star']]) {
    key(page, k, {ctrlKey: true, ...mods});
    assert.equal(page.board.currentTool, tool);
  }
  key(page, 'f', {ctrlKey: true});
  assert.equal(page.board.isFilled, true);

  page.board.setTool('select');
  drag(input, [0, 0], [50, 50]);
  key(page, 'c', {ctrlKey: true});
  key(page, 'v', {ctrlKey: true});
  assert.deepEqual(xy(page.board.drawingHistory[1]), [[30, 30], [40, 30]]);
  assert.equal(page.board.drawingHistory[2].type, 'paste');
  key(page, 'x', {ctrlKey: true});
  assert.equal(page.board.drawingHistory.at(-1).type, 'delete');
  assert.equal(page.statuses.at(-1), 'Selection cut');

  drag(input, [0, 0], [50, 50]);
  key(page, 'Escape');
  assert.deepEqual(plain(page.board.selectedStrokes), []);
  assert.equal(page.board.selectionRect, null);
  drag(input, [0, 0], [50, 50]);
  key(page, 'Delete');
  assert.equal(page.board.drawingHistory.at(-1).type, 'delete');

  const length = page.board.drawingHistory.length;
  page.board.setReadonly(true);
  key(page, 'z', {ctrlKey: true});
  assert.equal(page.board.drawingHistory.length, length);
});

// Count how often strokes already on the board are drawn
function countSceneDraws(page) {
  const draws = {count: 0};
  const drawStroke = page.board.drawStroke.bind(page.board);
  page.board.drawStroke = (stroke, ...rest) => {
    if (stroke !== page.board.currentStroke) draws.count++;
    drawStroke(stroke, ...rest);
  };
  return draws;
}

test('dragging draws the existing strokes once, not on every move', () => {
  const page = whiteboard();
  const input = devices.mouse(page);
  drag(input, [10, 10], [20, 10]);
  drag(input, [10, 30], [20, 30]);
  const scene = countSceneDraws(page);
  input.down(50, 50);
  for (let x = 51; x <= 70; x++) input.move(x, 50);
  assert.equal(scene.count, 2);
  input.up(70, 50);
  input.down(80, 80);
  input.move(90, 90);
  assert.equal(scene.count, 5, 'a new drag redraws the scene with the previous stroke');
});

test('a full redraw during a drag discards the cached scene', () => {
  const page = whiteboard();
  const input = devices.mouse(page);
  drag(input, [10, 10], [20, 10]);
  const scene = countSceneDraws(page);
  input.down(50, 50);
  input.move(55, 50);
  input.move(60, 50);
  assert.equal(scene.count, 1);
  key(page, 'z', {ctrlKey: true});
  const afterUndo = scene.count;
  input.move(65, 50);
  input.move(70, 50);
  assert.equal(afterUndo, 1, 'nothing left on the board after undo');
  assert.equal(page.board.gestureLayerValid, true);
  drag(input, [100, 100], [110, 110]);
  page.board.flipHorizontal();
  assert.equal(page.board.gestureLayerValid, false);
});

test('Escape cancels a selection box mid-drag', () => {
  const page = whiteboard();
  const input = devices.mouse(page);
  drag(input, [10, 10], [20, 10]);
  page.board.setTool('select');
  input.down(0, 0);
  input.move(50, 50);
  key(page, 'Escape');
  input.move(60, 60);
  input.up(60, 60);
  assert.equal(page.board.isSelecting, false);
  assert.deepEqual(plain(page.board.selectedStrokes), []);
  assert.equal(page.board.selectionRect, null);
});

test('saved drawings load back with their view and transforms', () => {
  const page = whiteboard();
  drag(devices.mouse(page), [10, 10], [20, 10]);
  page.board.flipHorizontal();
  page.board.rotateClockwise();
  Object.assign(page.board, {scale: 2, offsetX: 420, offsetY: 210});
  const saved = page.board.saveToJSON();
  const copy = whiteboard();
  assert.equal(copy.board.loadFromJSON(saved), true);
  for (const field of ['scale', 'offsetX', 'offsetY', 'flipX', 'flipY', 'rotation']) {
    assert.equal(copy.board[field], page.board[field]);
  }
  assert.deepEqual(xy(copy.board.drawingHistory[0]), [[10, 10], [20, 10]]);
  assert.equal(copy.board.loadFromJSON('{"version": 2}'), false);
});

test('drawing positions account for flip and rotation', () => {
  const page = whiteboard();
  Object.assign(page.board, {offsetX: 400, offsetY: 200});
  page.board.flipHorizontal();
  drag(devices.mouse(page), [410, 220], [420, 220]);
  assert.deepEqual(xy(page.board.drawingHistory[0]), [[-10, 20], [-20, 20]]);
  page.board.resetTransformations();
  page.board.rotateClockwise();
  drag(devices.mouse(page), [410, 220], [420, 220]);
  const rounded = xy(page.board.drawingHistory[1]).map(p => p.map(v => Math.round(v) + 0));
  assert.deepEqual(rounded, [[20, -10], [20, -20]]);
});
