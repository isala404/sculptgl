import yagui from 'yagui';
import TR from 'gui/GuiTR';
import GuiBackground from 'gui/GuiBackground';
import GuiCamera from 'gui/GuiCamera';
import GuiConfig from 'gui/GuiConfig';
import GuiFiles from 'gui/GuiFiles';
import GuiMesh from 'gui/GuiMesh';
import GuiTopology from 'gui/GuiTopology';
import GuiRendering from 'gui/GuiRendering';
import GuiScene from 'gui/GuiScene';
import GuiSculpting from 'gui/GuiSculpting';
import GuiStates from 'gui/GuiStates';
import GuiTablet from 'gui/GuiTablet';
import ShaderContour from 'render/shaders/ShaderContour';

import Export from 'files/Export';

class Gui {

  constructor(main) {
    this._main = main;

    this._guiMain = null;
    this._sidebar = null;
    this._topbar = null;

    this._ctrlTablet = null;
    this._ctrlFiles = null;
    this._ctrlScene = null;
    this._ctrlStates = null;
    this._ctrlCamera = null;
    this._ctrlBackground = null;

    this._ctrlSculpting = null;
    this._ctrlTopology = null;
    this._ctrlRendering = null;

    this._ctrlNotification = null;

    this._ctrls = []; // list of controllers

    // upload
    this._notifications = {};
    this._xhrs = {};
  }

  initGui() {
    this.deleteGui();

    this._guiMain = new yagui.GuiMain(this._main.getViewport(), this._main.onCanvasResize.bind(this._main));

    var ctrls = this._ctrls;
    ctrls.length = 0;
    var idc = 0;

    // Initialize the topbar
    this._topbar = this._guiMain.addTopbar();
    ctrls[idc++] = this._ctrlFiles = new GuiFiles(this._topbar, this);
    // this.initPrint(this._topbar);
    ctrls[idc++] = this._ctrlScene = new GuiScene(this._topbar, this);
    ctrls[idc++] = this._ctrlStates = new GuiStates(this._topbar, this);
    ctrls[idc++] = this._ctrlBackground = new GuiBackground(this._topbar, this);
    ctrls[idc++] = this._ctrlCamera = new GuiCamera(this._topbar, this);
    // TODO find a way to get pressure event
    ctrls[idc++] = this._ctrlTablet = new GuiTablet(this._topbar, this);
    ctrls[idc++] = this._ctrlConfig = new GuiConfig(this._topbar, this);
    ctrls[idc++] = this._ctrlMesh = new GuiMesh(this._topbar, this);


    // Initialize the sidebar
    this._sidebar = this._guiMain.addRightSidebar();
    ctrls[idc++] = this._ctrlRendering = new GuiRendering(this._sidebar, this);
    ctrls[idc++] = this._ctrlTopology = new GuiTopology(this._sidebar, this);
    ctrls[idc++] = this._ctrlSculpting = new GuiSculpting(this._sidebar, this);

    // gui extra
    var extra = this._topbar.addExtra();
    // Extra : Настройка интерфейса
    extra.addTitle(TR('contour'));
    extra.addColor(TR('contourColor'), ShaderContour.color, this.onContourColor.bind(this));

    extra.addTitle(TR('resolution'));
    extra.addSlider('', this._main._pixelRatio, this.onPixelRatio.bind(this), 0.5, 2.0, 0.02);

    this.addAboutButton();

    // AI Settings Menu
    this._ctrlAISettings = this.initAISettings(this._topbar);
    this.addAIPromptInput();

    this.updateMesh();
    this.setVisibility(true);

    if (window.postprocessGui) window.postprocessGui();
  }

  getNotification(notifName) {
    var notif = this._notifications[notifName];
    if (!notif) {
      notif = this._topbar.addMenu();
      notif.isVisible = function () {
        return !this.domContainer.hidden;
      };
      notif.setMessage = function (msg) {
        this.domContainer.innerHTML = msg;
        this.setVisibility(!!msg);
      };

      notif.domContainer.style.color = 'red';
      notif.setMessage('');

      this._notifications[notifName] = notif;
      return notif;
    }

    if (this._xhrs[notifName] && notif.isVisible()) {
      if (window.confirm('Abort ' + notifName + ' previous upload?')) {
        this._xhrs[notifName].abort();
        this._xhrs[notifName].isAborted = true;
        notif.setMessage(null);
      }
      return;
    }

    return notif;
  }

  initPrint(guiParent) {
    var menu = guiParent.addMenu('Print it!');
    // menu.addButton('with Sculpteo', this, 'exportSculpteo');
    menu.addButton('Go to Materialise!', this, 'exportMaterialise');
  }

  exportSculpteo() {
    this._export('sculpteo');
  }

  exportMaterialise() {
    if (window.confirm('A new webpage will be opened. Start upload?')) {
      this._export('materialise');
    }
  }

  exportSketchfab() {
    this._export('sketchfab');
  }

  _export(notifName) {
    var mesh = this._main.getMesh();
    if (!mesh) return;

    var notif = this.getNotification(notifName);
    if (!notif) return;

    var fName = 'export' + notifName.charAt(0).toUpperCase() + notifName.slice(1);
    this._xhrs[notifName] = Export[fName](this._main, notif);
  }

  onPixelRatio(val) {
    this._main._pixelRatio = val;
    this._main.onCanvasResize();
  }

  onContourColor(col) {
    ShaderContour.color[0] = col[0];
    ShaderContour.color[1] = col[1];
    ShaderContour.color[2] = col[2];
    ShaderContour.color[3] = col[3];
    this._main.render();
  }

  addAboutButton() {
    var ctrlAbout = this._topbar.addMenu();
    ctrlAbout.domContainer.innerHTML = TR('about');
    ctrlAbout.domContainer.addEventListener('mousedown', function () {
      window.open('http://stephaneginier.com', '_blank');
    });
  }

  addAIPromptInput() {
    var ctrlPrompt = this._topbar.addMenu();
    ctrlPrompt.domContainer.style.position = 'relative';
    
    // Create input element
    var promptInput = document.createElement('input');
    promptInput.type = 'text';
    promptInput.placeholder = 'Enter AI prompt...';
    promptInput.value = this._main.getAIPrompt() || '';
    promptInput.style.cssText = `
      padding: 4px 8px;
      border: 1px solid #ccc;
      border-radius: 4px;
      background: white;
      color: black;
      font-size: 12px;
      width: 200px;
      margin: 2px 4px;
      outline: none;
    `;
    
    // Prevent GUI framework from capturing events
    promptInput.addEventListener('mousedown', (e) => {
      e.stopPropagation();
    });
    
    promptInput.addEventListener('mouseup', (e) => {
      e.stopPropagation();
    });
    
    promptInput.addEventListener('click', (e) => {
      e.stopPropagation();
      promptInput.focus();
    });
    
    // Handle input changes
    promptInput.addEventListener('input', (e) => {
      e.stopPropagation();
      this._main.setAIPrompt(promptInput.value);
    });
    
    // Handle key events and prevent them from propagating to the main app
    promptInput.addEventListener('keydown', (e) => {
      e.stopPropagation();
      if (e.key === 'Enter') {
        promptInput.blur();
      }
    });
    
    promptInput.addEventListener('keyup', (e) => {
      e.stopPropagation();
    });
    
    promptInput.addEventListener('keypress', (e) => {
      e.stopPropagation();
    });
    
    // Handle focus events
    promptInput.addEventListener('focus', (e) => {
      e.stopPropagation();
      // Signal to main app that GUI has focus
      this._main._focusGui = true;
    });
    
    promptInput.addEventListener('blur', (e) => {
      e.stopPropagation();
      // Signal to main app that GUI lost focus
      this._main._focusGui = false;
    });
    
    // Clear the container and add the input
    ctrlPrompt.domContainer.innerHTML = '';
    ctrlPrompt.domContainer.appendChild(promptInput);
    
    // Store reference for potential updates
    this._promptInput = promptInput;
  }

  updateAIPromptInput() {
    if (this._promptInput) {
      this._promptInput.value = this._main.getAIPrompt() || '';
    }
  }

  initAISettings(guiParent) {
    var menu = guiParent.addMenu('AI Settings');
    
    // Style dropdown
    var styleOptions = [];
    styleOptions[0] = 'Basic';
    styleOptions[1] = 'Hairy Cute';
    var currentStyleIndex = this._main._aiStyle === 'basic' ? 0 : 1;
    menu.addCombobox('Style', currentStyleIndex, this.onStyleChange.bind(this), styleOptions);
    
    // AI Strength slider (0-100)
    menu.addSlider('AI Strength', this._main._aiStrength, this.onAIStrengthChange.bind(this), 0, 100, 1);
    
    // Randomize button
    menu.addButton('Randomize', this, 'onRandomizeSeed');
    
    return menu;
  }

  onStyleChange(value) {
    // Convert numeric index back to string value
    var styleValue = value === 0 ? 'basic' : 'hairy cute';
    this._main.setAIStyle(styleValue);
    console.log('AI Style changed to:', styleValue);
    // Add any additional logic for style changes here
  }

  onAIStrengthChange(value) {
    this._main.setAIStrength(value);
    console.log('AI Strength changed to:', value);
    // Add any additional logic for AI strength changes here
  }

  onRandomizeSeed() {
    var newSeed = Math.floor(Math.random() * 99000) + 1000;
    this._main.setAISeed(newSeed);
    console.log('AI Seed randomized to:', newSeed);
    // Add any additional logic for seed randomization here
  }

  updateMesh() {
    this._ctrlRendering.updateMesh();
    this._ctrlTopology.updateMesh();
    this._ctrlSculpting.updateMesh();
    this._ctrlScene.updateMesh();
    this.updateMeshInfo();
  }

  updateMeshInfo() {
    this._ctrlMesh.updateMeshInfo();
  }

  getFlatShading() {
    return this._ctrlRendering.getFlatShading();
  }

  getWireframe() {
    return this._ctrlRendering.getWireframe();
  }

  getShaderType() {
    return this._ctrlRendering.getShaderType();
  }

  addAlphaOptions(opts) {
    this._ctrlSculpting.addAlphaOptions(opts);
  }

  deleteGui() {
    if (!this._guiMain || !this._guiMain.domMain.parentNode)
      return;
    this.callFunc('removeEvents');
    this.setVisibility(false);
    this._guiMain.domMain.parentNode.removeChild(this._guiMain.domMain);
  }

  setVisibility(bool) {
    this._guiMain.setVisibility(bool);
  }

  callFunc(func, event) {
    for (var i = 0, ctrls = this._ctrls, nb = ctrls.length; i < nb; ++i) {
      var ct = ctrls[i];
      if (ct && ct[func])
        ct[func](event);
    }
  }
}

export default Gui;
