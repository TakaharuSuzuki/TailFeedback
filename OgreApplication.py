import sys
import os
import os.path
import ogre.renderer.OGRE as ogre
import ogre.io.OIS as OIS
import math
import ctypes

def getPluginPath():
    """ Return the absolute path to a valid plugins.cfg file.
    Look for plugins.cfg followed by plugins.cfg.nt|linux|mac
    in the current directory, BCPyOgreRenderer subdirectory, and parent directory.
    """
    suffix = 'mac' if os.sys.platform == 'darwin' else os.name
    search_dirs = [  os.getcwd(),
                     os.path.join(os.getcwd(), 'BCPyOgreRenderer'),
                     os.path.join(os.getcwd(), '..'),
                   ]
    for search_dir in search_dirs:
        paths = [os.path.join(search_dir, 'plugins.cfg'),
                os.path.join(search_dir, 'plugins.cfg.'+suffix)]
        for path in paths:
            if os.path.exists(path):
                return path

    sys.stderr.write("\n"
        "** Warning: Unable to locate a suitable plugins.cfg file.\n"
        "** Warning: Please check your ogre installation and copy a\n"
        "** Warning: working plugins.cfg file to the current directory.\n\n")
    raise ogre.Exception(0, "can't locate a suitable 'plugins' file", "")

def isUnitTest():
    """ use an environment variable to define that we need to do unittesting"""
    env = os.environ
    if env.has_key ("PythonOgreUnitTestPath"):
        return True
    return False

def UnitTest_Duration():
    return 5

def UnitTest_Screenshot():
    if isUnitTest():
        env = os.environ
        path = env["PythonOgreUnitTestPath"]
        parentpath = os.getcwd().split(os.path.sep)[-1] # get the last part of the parent directory
        filename = parentpath+'.'+ sys.modules['__main__'].__file__.split('.')[0] # file name is parent.demo.xx
        path = os.path.join ( path, filename )
        return path
    else:
        return "test"

class Application(object):
    debugText=""
    app_title = "MyApplication"

    def fakeInit(self):
        """Set some self variables that would normally be set by the BCPy Renderer wrapper."""
        import BCPy2000.AppTools.Coords as Coords
        self._plugins_path = None
        self._resource_path = None
        self._coords = Coords.Box(left=0, top=0, width=800, height=600, sticky=True, anchor='top left')
        self._screen_scale = 0.9
        self._screen_params = {
                                "monitorIndex": 0,
                                "left": 0,
                                "top": 0,
                                "title": "MyApplication"
                               }
        self.hmd = None

    def go(self):
        self.createRoot()
        self.defineResources()
        self.setupRenderSystem()
        self.createRenderWindow()
        self.initializeResourceGroups()
        self.setupScene()
        self.createFrameListener()

        #Add a demo object
        hand_ent = self.sceneManager.createEntity('hand.meshEntity', 'hand.mesh')
        hand_node = self.sceneManager.getRootSceneNode().createChildSceneNode(hand_ent.getName()+'Node', (0,0,-15))
        hand_node.attachObject(hand_ent)
        animState = hand_ent.getAnimationState('my_animation')
        animState.timePosition = 0.0
        animState.setLoop(True)
        animState.setEnabled(True)
        self.hand_ent = hand_ent

        #self.setupCEGUI()
        self.startRenderLoop()
        self.cleanUp()

    # The Root constructor for the ogre
    def createRoot(self):
        if self._plugins_path is None:
            self._plugins_path = getPluginPath()
        self.root = ogre.Root(self._plugins_path)

    # Here the resources are read from the resources.cfg
    def defineResources(self):
        rgm = ogre.ResourceGroupManager.getSingleton()
        cf = ogre.ConfigFile()
        if self._resource_path is None:
            self._resource_path = os.path.join(os.path.dirname(self._plugins_path),'resources.cfg')
        cf.load(self._resource_path)
        seci = cf.getSectionIterator()
        while seci.hasMoreElements():
            secName = seci.peekNextKey()
            settings = seci.getNext()
            for item in settings:
                typeName = item.key
                archName = item.value
                rgm.addResourceLocation(archName, typeName, secName)

    # Create and configure the rendering system (either DirectX or OpenGL) here
    def setupRenderSystem(self): #Delete ogre.cfg to show the config dialog box
        if not self.root.restoreConfig() and not self.root.showConfigDialog():
            raise Exception("User canceled the config dialog -> Application.setupRenderSystem()")

    # Create the render window
    def createRenderWindow(self):
        use_ogrecfg = True
        if use_ogrecfg:
            self.root.initialise(True, "BCPyOgre Window")
            self.renderWindow = self.root.getAutoCreatedWindow() #Should be 1280 x 800 if working on OVR dev kit.
        else: #This requires the BCPy application to setup the screen using its parameters during preflight
            self.root.initialise(False)
            hWnd = 0  # Get the hWnd of the application
            misc = ogre.NameValuePairList()
            misc["externalWindowHandle"] = str(int(hWnd))
            if self._screen_params["monitorIndex"] == -1:
                try:
                    self._screen_params["monitorIndex"] = self.root.getDisplayMonitorCount()-1 #Only newer versions of Ogre
                except:
                    import BCPy2000.AppTools.Displays as Displays
                    self._screen_params["monitorIndex"] = len(Displays.monitors())-1
            # misc["border"] = self._screen_params["border"] #Causes unexpected behavior
            misc["left"] = str(int(self._screen_params["left"]))
            misc["top"] = str(int(self._screen_params["top"]))
            misc["monitorIndex"] = str(int(self._screen_params["monitorIndex"]))
            if self._screen_scale:
                pass#TODO: Get the size of the monitor and scale it if a scale is provided
            scrw,scrh = int(self._coords.width), int(self._coords.height)
            self.renderWindow = self.root.createRenderWindow(self._screen_params["title"], scrw, scrh, False, misc)
        self.renderWindow.setDeactivateOnFocusChange(False)

    # Initialize the resources here (which were read from resources.cfg in defineResources()
    def initializeResourceGroups(self):
        ogre.TextureManager.getSingleton().setDefaultNumMipmaps(5)
        ogre.ResourceGroupManager.getSingleton().initialiseAllResourceGroups()

    # Now, create a scene here. Three things that MUST BE done are sceneManager, camera and
    # viewport initializations
    def setupScene(self):
        #Assume 1 ogre unit = 1 m since the oculus rift returns units that way.
        #Create and configure the scene manager
        self.sceneManager = self.root.createSceneManager(ogre.ST_GENERIC, "Default SceneManager")
        if self.hmd:
            rift_info = self.hmd.info
            #Create the l/r cameras
            self.cameraNode = self.sceneManager.getRootSceneNode().createChildSceneNode("StereoCameraNode")# Create camera node
            self.cameras = [self.sceneManager.createCamera(cam_string) for cam_string in ["CameraLeft", "CameraRight"]]# Create two cameras
            #Add the l/r viewports to the cameras
            self.viewPorts = [self.renderWindow.addViewport(self.cameras[ix], ix, 0.5*ix, 0, 0.5, 1) for ix in range(2)] #cam, z-ord, left, top, w, h
            for ix in range(2):
                self.viewPorts[ix].setBackgroundColour(ogre.ColourValue(0/255.0, 0/255.0, 0/255.0))
                
            #Configure the separate cameras
            #Set the l/r projection matrices (needs aspect, fov, center of lens rel to screen center)
            my_asp = rift_info['aspect'] if True else 0.8 #0.5*HRes/VRes = 0.8
            my_fovy = ogre.Radian(rift_info['yfovrad']) if True else ogre.Radian(ogre.Degree(110)) #2arctan( VScreenSize / (2*EyeToScreenDistance) )
            my_ipd = rift_info['ipd'] if True else 0.064
            my_znear = rift_info['eye_to_screen_distance'] if True else 0.01
            my_zfar = 10000.0
            my_pco = rift_info['projection_center_offset'] if True else 0.14529906
            my_proj = [ogre.Matrix4(*[it for sl in rift_info['proj_mats'][lr_str] for it in sl]) for lr_str in ['left','right']]
            #P for screen center = [[1/(my_asp * tan(my_fovy/2)), 0, 0, 0], [0, 1/(my_asp * tan(my_fovy/2)), 0, 0], [0, 0, zfar/(znear-zfar), zfar*znear/(znear-zfar)], [0, 0, -1, 0]]
            #P for lens center = H*P where H = [[1, 0, 0, h], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]] (-h for right eye; h=lens center relative to screen center)
            #V for eye location
            for ix in range(2):
                self.cameraNode.attachObject(self.cameras[ix])
                self.cameras[ix].setNearClipDistance(my_znear)
                self.cameras[ix].setFarClipDistance(my_zfar)
                self.cameras[ix].setPosition((ix*2-1) * my_ipd * 0.5, 0.075, 0.045)
                self.cameras[ix].setAspectRatio(my_asp)
                self.cameras[ix].setFOVy(my_fovy)
                proj = ogre.Matrix4(ogre.Quaternion())
                proj.setTrans(ogre.Vector3(-my_pco * (2 * ix - 1), 0, 0)) #adjust for lens centers
                self.cameras[ix].setCustomProjectionMatrix(True, proj * self.cameras[ix].getProjectionMatrix())
                #self.cameras[ix].setCustomProjectionMatrix(True, my_proj[ix])
                
            #Set the barrel distortion compensation.
            my_distortion = rift_info['distortion'] if True else [1.0, 0.22, 0.24, 0]
            hmdwarp = ogre.Vector4(my_distortion[0], my_distortion[1], my_distortion[2], my_distortion[3])
            matLeft = ogre.MaterialManager.getSingleton().getByName("Ogre/Compositor/Oculus")
            mats = [matLeft, matLeft.clone("Ogre/Compositor/Oculus/Right")]
            pParams = [mat.getTechnique(0).getPass(0).getFragmentProgramParameters() for mat in mats]
            self.compositors = []
            scaleFactor = 1.0 / rift_info['distortion_scale']
            my_chrom_ab = rift_info['chrom_ab']
            my_chrom_ab = ogre.Vector4(my_chrom_ab[0], my_chrom_ab[1], my_chrom_ab[2], my_chrom_ab[3])
            for ix in range(2):
                pParam = pParams[ix]
                pParam.setNamedConstant("LensCentre", 0.5 + ((1-2*ix)*my_pco)*0.5) #x + (w + Distortion.XCenterOffset * 0.5f)*0.5f, y+h*0.5f
                pParam.setNamedConstant("HmdWarpParam", hmdwarp)
                pParam.setNamedConstant("ChromAbParam", my_chrom_ab)
                aspr = self.cameras[ix].getAspectRatio()
                scaleIn = (ctypes.c_float*2)(*[2.0, 2.0/aspr])
                pParam.setNamedConstantFloat("ScaleIn", ctypes.addressof(scaleIn), 1)
                scale = (ctypes.c_float*2)(*[0.5*scaleFactor, 0.5*scaleFactor*aspr])
                pParam.setNamedConstantFloat("Scale", ctypes.addressof(scale), 1)
                self.compositors.append(ogre.CompositorManager.getSingleton().addCompositor(self.viewPorts[ix], "OculusLeft" if ix==0 else "OculusRight"))
                self.compositors[ix].setEnabled(True)
            comp = ogre.CompositorManager.getSingleton().getByName("OculusRight")
            comp.getTechnique(0).getOutputTargetPass().getPass(0).setMaterialName("Ogre/Compositor/Oculus/Right")

        else:
            #Create and configure the camera
            #Think about doing orthographic camera
            self.camera = self.sceneManager.createCamera("Camera")
            #Create and configure the viewPort
            self.viewPort = self.renderWindow.addViewport(self.camera)
            #self.viewPort.setBackgroundColour(self._bgcolor)

            #Give the camera a default position, but your application should specify if you are using 3d objects.
            #self.camera.setPosition( ogre.Vector3(0, 0, 0) )
            #self.camera.lookAt( ogre.Vector3(0, 0, -1) )
            self.camera.setNearClipDistance(0.01)
            self.camera.setAutoAspectRatio(True);

        light = self.sceneManager.createLight("light");
        light.setType(ogre.Light.LT_DIRECTIONAL)
        light.setDirection(-0.577, -0.577, -0.577)
        light.setDiffuseColour(ogre.ColourValue(1.0, 1.0, 1.0))
        self.sceneManager.setAmbientLight(ogre.ColourValue(0.4, 0.4, 0.4))
        #self.sceneManager.setSkyDome(True, 'Examples/CloudySky',4, 8)
        #self.sceneManager.setFog( ogre.FOG_EXP, ogre.ColourValue(1,1,1),0.0005)
        
        #Add a light source
        #self.light = self.sceneManager.createLight("Light1")
        #light.type = ogre.Light.LT_POINT
        #self.light.setPosition ( ogre.Vector3(1, 5, 0.10) )
        #self.light.diffuseColour = 0.5, 0.5, 0.5
        #self.light.specularColour = 0.3, 0.3, 0.3

        #Create a 2D overlay for text and 2D objects.
        self.overlayManager = ogre.OverlayManager.getSingleton()
        top_overlay = self.overlayManager.create("TopOverlay")
        screen_panel = self.overlayManager.createOverlayElement("Panel", "screen")
        #screen_panel.setPosition(0, 0)
        #screen_panel.setDimensions(1, 1)
        #screen_panel.setMetricsMode(ogre.GMM_PIXELS)
        top_overlay.add2D(screen_panel)
        #VisionEgg uses pixels and bottom left as origin so let's create such a panel for functions that emulate VisionEgg behavior.
        ve_panel = self.overlayManager.createOverlayElement("Panel", "visionegg")
        #ve_panel.setMetricsMode(ogre.GMM_PIXELS)
        #ve_panel.setVerticalAlignment(ogre.GVA_BOTTOM)
        #ve_panel.setHorizontalAlignment(ogre.GHA_LEFT)
        screen_panel.addChild(ve_panel)
        top_overlay.show()

        #self.coordinate_mapping = self._coordinate_mapping

    def createFrameListener(self):
        """Creates the FrameListener."""
        if self.hmd:
            self.hmdFrameListener = HMDFrameListener(self.hmd, self.cameraNode)
            self.root.addFrameListener(self.hmdFrameListener)
            camera = self.cameras[0]
        else:
            camera = self.camera
        #,self.frameListener, self.frameListener.Mouse
        self.frameListener = FrameListener(self.renderWindow, camera)
        #self.frameListener.unittest = self.unittest
        #self.frameListener.showDebugOverlay(True)
        self.frameListener.showDebugOverlay(False)
        self.root.addFrameListener(self.frameListener)

    def startRenderLoop(self):
        self.root.startRendering()

    def cleanUp(self):
        # Clean up Ogre
        self.root.shutdown()
        del self.root
        
class HMDFrameListener(ogre.FrameListener):
    def __init__(self, hmd, cameraNode):
        ogre.FrameListener.__init__(self)
        self.hmd = hmd
        self.cameraNode = cameraNode

    def frameRenderingQueued ( self, evt ):
        new_quat = self.hmd.rot_quat
        #newOrient = ogre.Quaternion() * new_quat
        self.cameraNode.setOrientation(ogre.Quaternion(new_quat[3], new_quat[0], new_quat[1], new_quat[2]))
        return True

class FrameListener(ogre.FrameListener, ogre.WindowEventListener):
    """A default frame listener, which takes care of basic mouse and keyboard
    input."""

    def __init__(self, renderWindow, camera, bufferedKeys = False, bufferedMouse = False, bufferedJoy = False):
        ogre.FrameListener.__init__(self)
        ogre.WindowEventListener.__init__(self)
        self.camera = camera
        self.renderWindow = renderWindow
        self.statisticsOn = True
        self.numScreenShots = 0
        self.timeUntilNextToggle = 0
        self.sceneDetailIndex = 0
        self.moveScale = 0.0
        self.rotationScale = 0.0
        self.translateVector = ogre.Vector3(0.0,0.0,0.0)
        self.filtering = ogre.TFO_BILINEAR
        self.showDebugOverlay(True)
        self.rotateSpeed =  ogre.Degree(36)
        self.moveSpeed = 10.0
        self.rotationSpeed = 8.0
        self.displayCameraDetails = False
        self.bufferedKeys = bufferedKeys
        self.bufferedMouse = bufferedMouse
        self.rotationX = ogre.Degree(0.0)
        self.rotationY = ogre.Degree(0.0)
        self.bufferedJoy = bufferedJoy
        self.shouldQuit = False # set to True to exit..
        self.MenuMode = False   # lets understand a simple menu function
        self.unittest = isUnitTest()
        self.unittest_duration = UnitTest_Duration()  # seconds before screen shot a exit
#         self.unittest_screenshot = sys.modules['__main__'].__file__.split('.')[0]     # file name for unittest screenshot
        self.unittest_screenshot = UnitTest_Screenshot()
        ## we can tell if we are using OgreRefapp based upon the camera class

        if self.camera.__class__ == ogre.Camera:
            self.RefAppEnable = False
        else:
            self.RefAppEnable = True
        self._setupInput()
        self._registeredAnimStates = []

    def __del__ (self ):
        #ogre.WindowEventUtilities.removeWindowEventListener(self.renderWindow, self)
        self.windowClosed(self.renderWindow)

    def _inputSystemParameters (self ):
        """ ovreride to extend any OIS system parameters
        """
        return []

    def _setupInput(self):
        # ignore buffered input

        # FIXME: This should be fixed in C++ propbably
        import platform
        int64 = False
        for bit in platform.architecture():
            if '64' in bit:
                int64 = True
        if int64:
            windowHnd = self.renderWindow.getCustomAttributeUnsignedLong("WINDOW")
        else:
            windowHnd = self.renderWindow.getCustomAttributeInt("WINDOW")

        #Set initial mouse clipping size
        self.windowResized(self.renderWindow)

        self.showDebugOverlay(True)

        #Register as a Window listener
        ogre.WindowEventUtilities.addWindowEventListener(self.renderWindow, self);



    def setMenuMode(self, mode):
        self.MenuMode = mode

    def _UpdateSimulation( self, frameEvent ):
        # create a real version of this to update the simulation
        pass

    def windowResized (self, rw):
        dummyint = 0
        width, height, depth, left, top= rw.getMetrics(dummyint,dummyint,dummyint, dummyint, dummyint)  # Note the wrapped function as default needs unsigned int's
        # ms = self.Mouse.getMouseState()
        # ms.width = width
        # ms.height = height

    def windowClosed(self, rw):
        #Only close for window that created OIS (mWindow)
        if( rw == self.renderWindow ):
            if( self.InputManager ):
                self.InputManager.destroyInputObjectMouse( self.Mouse )
                self.InputManager.destroyInputObjectKeyboard( self.Keyboard )
                if self.Joy:
                    self.InputManager.destroyInputObjectJoyStick( self.Joy )
                OIS.InputManager.destroyInputSystem(self.InputManager)
                self.InputManager=None

    ## NOTE the in Ogre 1.6 (1.7) this is changed to frameRenderingQueued !!!
    def frameRenderingQueued ( self, evt ):
        if(self.renderWindow.isClosed() or self.shouldQuit ):
            return False
        if self.unittest:
            self.unittest_duration -= evt.timeSinceLastFrame
            if self.unittest_duration < 0:
                self.renderWindow.writeContentsToFile(self.unittest_screenshot + '.jpg')
                return False

        return True


#     def frameStarted(self, frameEvent):
#         return True
#
#         if self.timeUntilNextToggle >= 0:
#             self.timeUntilNextToggle -= frameEvent.timeSinceLastFrame
#
#         if frameEvent.timeSinceLastFrame == 0:
#             self.moveScale = 1
#             self.rotationScale = 0.1
#         else:
#             self.moveScale = self.moveSpeed * frameEvent.timeSinceLastFrame
#             self.rotationScale = self.rotationSpeed * frameEvent.timeSinceLastFrame
#
#         self.rotationX = ogre.Degree(0.0)
#         self.rotationY = ogre.Degree(0.0)
#         self.translateVector = ogre.Vector3(0.0, 0.0, 0.0)
#         if not self._processUnbufferedKeyInput(frameEvent):
#             return False
#
#         if not self.MenuMode:   # if we are in Menu mode we don't move the camera..
#             self._processUnbufferedMouseInput(frameEvent)
#         self._moveCamera()
#         # Perform simulation step only if using OgreRefApp.  For simplicity create a function that simply does
#         ###  "OgreRefApp.World.getSingleton().simulationStep(frameEvent.timeSinceLastFrame)"
#
#         if  self.RefAppEnable:
#             self._UpdateSimulation( frameEvent )
#         return True

    def frameEnded(self, frameEvent):
        if self.statisticsOn:
            self._updateStatistics()
        return True

    def showDebugOverlay(self, show):
        """Turns the debug overlay (frame statistics) on or off."""
        overlay = ogre.OverlayManager.getSingleton().getByName('POCore/DebugOverlay')
        if overlay is None:
            self.statisticsOn = False
            ogre.LogManager.getSingleton().logMessage( "ERROR in sf_OIS.py: Could not find overlay POCore/DebugOverlay" )
            return
        if show:
            overlay.show()
        else:
            overlay.hide()

    def _processUnbufferedKeyInput(self, frameEvent):
        if self.Keyboard.isKeyDown(OIS.KC_A):
            self.translateVector.x = -self.moveScale

        if self.Keyboard.isKeyDown(OIS.KC_D):
            self.translateVector.x = self.moveScale

        if self.Keyboard.isKeyDown(OIS.KC_UP) or self.Keyboard.isKeyDown(OIS.KC_W):
            self.translateVector.z = -self.moveScale

        if self.Keyboard.isKeyDown(OIS.KC_DOWN) or self.Keyboard.isKeyDown(OIS.KC_S):
            self.translateVector.z = self.moveScale

        if self.Keyboard.isKeyDown(OIS.KC_PGUP):
            self.translateVector.y = self.moveScale

        if self.Keyboard.isKeyDown(OIS.KC_PGDOWN):
            self.translateVector.y = - self.moveScale

        if self.Keyboard.isKeyDown(OIS.KC_RIGHT):
            self.rotationX = - self.rotationScale

        if self.Keyboard.isKeyDown(OIS.KC_LEFT):
            self.rotationX = self.rotationScale

        #=======================================================================
        # if self.Keyboard.isKeyDown(OIS.KC_ESCAPE) or self.Keyboard.isKeyDown(OIS.KC_Q):
        #    return False
        #=======================================================================

        if( self.Keyboard.isKeyDown(OIS.KC_F) and self.timeUntilNextToggle <= 0 ):
            self.statisticsOn = not self.statisticsOn
            self.showDebugOverlay(self.statisticsOn)
            self.timeUntilNextToggle = 1

        if self.Keyboard.isKeyDown(OIS.KC_T) and self.timeUntilNextToggle <= 0:
            if self.filtering == ogre.TFO_BILINEAR:
                self.filtering = ogre.TFO_TRILINEAR
                self.Aniso = 1
            elif self.filtering == ogre.TFO_TRILINEAR:
                self.filtering = ogre.TFO_ANISOTROPIC
                self.Aniso = 8
            else:
                self.filtering = ogre.TFO_BILINEAR
                self.Aniso = 1

            ogre.MaterialManager.getSingleton().setDefaultTextureFiltering(self.filtering)
            ogre.MaterialManager.getSingleton().setDefaultAnisotropy(self.Aniso)
            self.showDebugOverlay(self.statisticsOn)
            self.timeUntilNextToggle = 1

        if self.Keyboard.isKeyDown(OIS.KC_SYSRQ) and self.timeUntilNextToggle <= 0:
            path = 'screenshot_%d.png' % self.numScreenShots
            self.numScreenShots += 1
            self.renderWindow.writeContentsToFile(path)
            Application.debugText = 'screenshot taken: ' + path
            self.timeUntilNextToggle = 0.5

        if self.Keyboard.isKeyDown(OIS.KC_R) and self.timeUntilNextToggle <= 0:
            detailsLevel = [ ogre.PM_SOLID,
                             ogre.PM_WIREFRAME,
                             ogre.PM_POINTS ]
            self.sceneDetailIndex = (self.sceneDetailIndex + 1) % len(detailsLevel)
            self.camera.polygonMode=detailsLevel[self.sceneDetailIndex]
            self.timeUntilNextToggle = 0.5

        if self.Keyboard.isKeyDown(OIS.KC_F) and self.timeUntilNextToggle <= 0:
            self.statisticsOn = not self.statisticsOn
            self.showDebugOverlay(self.statisticsOn)
            self.timeUntilNextToggle = 1

        if self.Keyboard.isKeyDown(OIS.KC_P) and self.timeUntilNextToggle <= 0:
            self.displayCameraDetails = not self.displayCameraDetails
            if not self.displayCameraDetails:
                Application.debugText = ""

        if self.displayCameraDetails:
            # Print camera details
            pos = self.camera.getDerivedPosition()
            o = self.camera.getDerivedOrientation()
            Application.debugText = "P: %.3f %.3f %.3f O: %.3f %.3f %.3f %.3f"  \
                        % (pos.x,pos.y,pos.z, o.w,o.x,o.y,o.z)

        return True

    def _isToggleKeyDown(self, keyCode, toggleTime = 1.0):
        if self.Keyboard.isKeyDown(keyCode)and self.timeUntilNextToggle <=0:
            self.timeUntilNextToggle = toggleTime
            return True
        return False

    def _isToggleMouseDown(self, Button, toggleTime = 1.0):
        ms = self.Mouse.getMouseState()
        if ms.buttonDown( Button ) and self.timeUntilNextToggle <=0:
            self.timeUntilNextToggle = toggleTime
            return True
        return False

    def _processUnbufferedMouseInput(self, frameEvent):
        ms = self.Mouse.getMouseState()
        if ms.buttonDown( OIS.MB_Right ):
            self.translateVector.x += ms.X.rel * 0.13
            self.translateVector.y -= ms.Y.rel * 0.13
        else:
            self.rotationX = ogre.Degree(- ms.X.rel * 0.13)
            self.rotationY = ogre.Degree(- ms.Y.rel * 0.13)
        return True

    def _moveCamera(self):
        self.camera.yaw(self.rotationX)
        self.camera.pitch(self.rotationY)
#         try:
#             self.camera.translate(self.translateVector) # for using OgreRefApp
#         except AttributeError:
        self.camera.moveRelative(self.translateVector)

    def _updateStatistics(self):
        statistics = self.renderWindow
        self._setGuiCaption('POCore/AverageFps', 'Avg FPS: %u' % statistics.getAverageFPS())
        self._setGuiCaption('POCore/CurrFps', 'FPS: %u' % statistics.getLastFPS())
#         self._setGuiCaption('POCore/BestFps',
#                              'Best FPS: %f %d ms' % (statistics.getBestFPS(), statistics.getBestFrameTime()))
#         self._setGuiCaption('POCore/WorstFps',
#                              'Worst FPS: %f %d ms' % (statistics.getWorstFPS(), statistics.getWorstFrameTime()))
        self._setGuiCaption('POCore/NumTris', 'Trianges: %u' % statistics.getTriangleCount())
        self._setGuiCaption('POCore/NumBatches', 'Batches: %u' % statistics.batchCount)

        self._setGuiCaption('POCore/DebugText', Application.debugText)

    def _setGuiCaption(self, elementName, text):
        element = ogre.OverlayManager.getSingleton().getOverlayElement(elementName, False)
        ##d=ogre.UTFString("hell0")
        ##element.setCaption(d)

        #element.caption="hello"

        #element.setCaption("help")
        element.setCaption(text) # ogre.UTFString(text))


if __name__ == '__main__':
    import threading
    self = Application()
    def ogreFunc():
        try:
            self.fakeInit() #Fake the initialization that would happen from a BCPy2000 application.
            self.go()
        except ogre.OgreException, e:
            print e
    ogreThread = threading.Thread(target=ogreFunc)
    ogreThread.start()
    print ogreThread