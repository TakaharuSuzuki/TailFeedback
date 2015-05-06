'''
Created on Jun 22, 2013

@author: Chad
'''
import ogre.renderer.OGRE as ogre
import math

class StereoManager(object):
    def __init__(self, leftViewport, rightViewport=None, mode="SM_ANAGLYPH_RC"):
        self.mStereoMode = None
        self.mDebugPlane = None
        self.mDebugPlaneNode = None
        self.mLeftViewport = None
        self.mRightViewport = None
        self.mCamera = None
        self.mCompositorInstance = None
        self.mIsFocalPlaneFixed = False
        self.mScreenWidth = 1.0
        self.mEyesSpacing = 0.06
        self.mFocalLength = 10.0
        self.mFocalLengthInfinite = False
        self.mIsInversed = False
        self.mIsCustomProjection = False
        self.mLeftCustomProjection = ogre.Matrix4.IDENTITY
        self.mRightCustomProjection = ogre.Matrix4.IDENTITY
        self.mRightMask = 1 #TODO: ~((uint32)0)
        self.mLeftMask = self.mRightMask
        self.mAvailableModes = {}
        self.mAvailableModes["SM_ANAGLYPH_RC"] = {"mName":"ANAGLYPH_RED_CYAN", "mMaterialName":"Stereo/RedCyanAnaglyph", "mUsesCompositor": True}
        self.mAvailableModes["SM_ANAGLYPH_YB"] = {"mName":"ANAGLYPH_YELLOW_BLUE", "mMaterialName":"Stereo/YellowBlueAnaglyph", "mUsesCompositor": True}
        self.mAvailableModes["SM_INTERLACED_H"] = {"mName":"INTERLACED_HORIZONTAL", "mMaterialName":"Stereo/HorizontalInterlace", "mUsesCompositor": True}
        self.mAvailableModes["SM_INTERLACED_V"] = {"mName":"INTERLACED_VERTICAL", "mMaterialName":"Stereo/VerticalInterlace", "mUsesCompositor": True}
        self.mAvailableModes["SM_INTERLACED_CB"] = {"mName":"INTERLACED_CHECKBOARD", "mMaterialName":"Stereo/CheckboardInterlace", "mUsesCompositor": True}
        self.mAvailableModes["SM_DUALOUTPUT"] = {"mName":"DUALOUTPUT", "mMaterialName":"", "mUsesCompositor": False}
        self.mAvailableModes["SM_NONE"] = {"mName":"NONE", "mMaterialName":"", "mUsesCompositor": False}
        self.mRenderTargetList = {}

        self.mStereoMode = mode
        if not self.mStereoMode:
            return
        self.mCamera = leftViewport.getCamera()
        if self.mAvailableModes[self.mStereoMode]["mUsesCompositor"]:
            leftViewport, rightViewport = self.initCompositor(leftViewport, self.mAvailableModes[self.mStereoMode]["mMaterialName"])

        self.initListeners(leftViewport, rightViewport)

        #TODO: Do I need to maintain a separate list of renderTargets other than the main iterator?
        for k,v in self.mRenderTargetList: k.setAutoUpdated(False)

        infinite = self.mFocalLengthInfinite
        self.setFocalLength(self.mFocalLength)
        self.setFocalLengthInfinite(infinite)

        if self.mIsFocalPlaneFixed:
            self.updateCamera(0)

    def initListeners(self, leftViewport, rightViewport):
        self.mLeftCameraListener = StereoCameraListener(self, leftViewport, not self.mIsInversed)
        leftViewport.getTarget().addListener(self.mLeftCameraListener)
        self.mLeftViewport = leftViewport

        self.mRightCameraListener = StereoCameraListener(self, rightViewport, self.mIsInversed)
        rightViewport.getTarget().addListener(self.mRightCameraListener)
        self.mRightViewport = rightViewport

    def shutdownListeners(self):
        self.mLeftViewport.getTarget().removeListener(self.mLeftCameraListener)
        self.mLeftViewport = None
        self.mRightViewport.getTarget().removeListener(self.mRightCameraListener)
        self.mRightViewport = None

    def initCompositor(self, viewport, materialName):
        self.mCompositorViewport = viewport
        self.mCompositorInstance = ogre.CompositorManager.getSingleton().addCompositor(viewport, "Stereo/BaseCompositor")
        ogre.CompositorManager.getSingleton().setCompositorEnabled(viewport, "Stereo/BaseCompositor", True)
        mat = ogre.MaterialManager.getSingleton().getByName(materialName)
        self.mCompositorInstance.getTechnique().getOutputTargetPass().getPass(0).setMaterial(mat)
        out_left = self.mCompositorInstance.getRenderTarget("Stereo/Left").getViewport(0)
        out_right = self.mCompositorInstance.getRenderTarget("Stereo/Right").getViewport(0)
        #self.mDeviceLostListener = DeviceLostListener(self)
        #ogre.Root.getSingleton().getRenderSystem().addListener(self.mDeviceLostListener)
        return out_left, out_right

    def shutdownCompositor(self):
        ogre.CompositorManager.getSingleton().setCompositorEnabled(self.mCompositorViewport, "Stereo/BaseCompositor", False)
        ogre.CompositorManager.getSingleton().removeCompositor(self.mCompositorViewport, "Stereo/BaseCompositor")
        ogre.Root.getSingleton().getRenderSystem().removeListener(self.mDeviceLostListener)
        self.mCompositorInstance = None
        self.mCompositorViewport = None

    def shutdown(self):
        if not self.mStereoMode:
            return
        self.shutdownListeners()
        if self.mAvailableModes[self.mStereoMode]["mUsesCompositor"]: self.shutdownCompositor()
        #TODO: Change the mRenderTargetList autoUpdated
        self.mStereoMode = None

    def addRenderTargetDependency(self, renderTarget):
        if renderTarget in self.mRenderTargetList.keys(): return
        self.mRenderTargetList[renderTarget] = renderTarget.isAutoUpdated
        renderTarget.setAutoUpdated(False)

    def removeRenderTargetDependency(self, renderTarget):
        renderTarget.setAutoUpdated(self.mRenderTargetList[renderTarget])
        del self.mRenderTargetList[renderTarget]

    def createDebugPlane(self, sceneMgr, leftMaterialName = "", rightMaterialName = ""):
        if self.mDebugPlane:
            return

        self.mSceneMgr = sceneMgr
        screenPlane = ogre.Plane()
        screenPlane.normal = ogre.Vector3.UNIT_Z
        ogre.MeshManager.getSingleton().createPlane("Stereo/Plane", ogre.ResourceGroupManager.DEFAULT_RESOURCE_GROUP_NAME, screenPlane, 1,1,10,10)
        self.mDebugPlane = sceneMgr.createEntity("Stereo/DebugPlane", "Stereo/Plane")
        self.mLeftMaterialName = "Stereo/Wireframe" if leftMaterialName=="" else leftMaterialName
        self.mRightMaterialName = "Stereo/Wireframe" if rightMaterialName=="" else rightMaterialName
        self.mDebugPlaneNode = sceneMgr.getRootSceneNode().createChild("Stereo/DebugPlaneNode")
        self.mDebugPlaneNode.attachObject(self.mDebugPlane)
        self.enableDebugPlane(True)
        self.updateDebugPlane()

    def destroyDebugPlane(self):
        if self.mDebugPlane:
            parent = self.mDebugPlaneNode.getParent()
            parent.removeAndDestroyChild("Stereo/DebugPlaneNode")
            self.mDebugPlaneNode = None
            self.mSceneMgr.destroyEntity("Stereo/DebugPlane")
            self.mDebugPlane = None
            ogre.MeshManager.getSingleton().remove("Stereo/Plane")

    def enableDebugPlane(self, enable):
        if self.mDebugPlane: self.mDebugPlane.setVisible(enable)

    def toggleDebugPlane(self):
        if self.mDebugPlane: self.mDebugPlane.setVisible(self.mDebugPlane.isVisible())

    def updateDebugPlane(self):
        if self.mDebugPlaneNode and self.mCamera:
            actualFocalLength = self.mCamera.getFarClipDistance()*0.99 if self.mFocalLengthInfinite else self.mFocalLength
            pos = self.mCamera.getDerivedPosition()
            pos += self.mCamera.getDerivedDirection() * actualFocalLength
            self.mDebugPlaneNode.setPosition(pos)
            self.mDebugPlaneNode.setOrientation(self.mCamera.getDerivedOrientation())
            height = actualFocalLength * math.tan(self.mcamera.getFOVy()/2) * 2
            scale = ogre.Vector3.UNIT_SCALE
            scale.z = 1
            scale.y = height
            scale.x = height * self.mCamera.getAspectRatio()
            self.mDebugPlaneNode.setScale(scale)

    def getStereoMode(self):
        return self.mStereoMode

    def getCamera(self):
        return self.mCamera
    def setCamera(self, cam):
        self.mCamera = cam

    def getEyesSpacing(self):
        return self.mEyesSpacing
    def setEyesSpacing(self, l):
        self.mEyesSpacing = l

    def getFocalLength(self):
        return Infinity if self.mFocalLengthInfinite else self.mFocalLength
    def setFocalLength(self, l):
        if l==Infinity:
            self.setFocalLengthInfinite(True)
        else:
            self.setFocalLengthInfinite(False)
            old = self.mFocalLength
            self.mFocalLength = l
            if self.mCamera:
                self.mCamera.setFocalLength(self.mFocalLength)
                if self.mIsFocalPlaneFixed: self.updateCamera(self.mFocalLength - old)
                elif self.mDebugPlane: self.updateDebugPlane()

    def setFocalLengthInfinite(self, isInfinite=True):
        self.mFocalLengthInfinite = isInfinite
        if isInfinite: self.mIsFocalPlaneFixed = False
    def isFocalLengthInfinite(self):
        return self.mFocalLengthInfinite
    def fixFocalPlanePos(self, fix):
        self.mIsFocalPlaneFixed = fix
    def setScreenWidth(self, w):
        self.mScreenWidth = w
    def useScreenWidth(self, w):
        self.mScreenWidth = w
        self.mIsFocalPlaneFixed = True
        if self.mCamera: self.updateCamera(0)

    def setCustomProjectionMatrices(self, enable, leftMatrix, rightMatrix):
        self.mIsCustomProjection = enable
        self.mLeftCustomProjection = leftMatrix
        self.mRightCustomProjection = rightMatrix
    def getCustomProjectionMatrices(self):
        return self.mIsCustomProjection, self.mLeftCustomProjection, self.mRightCustomProjection

    def inverseStereo(self, inverse):
        self.mIsInversed = inverse
        self.mLeftCameraListener.mIsLeftEye = not self.mIsInversed
        self.mRightCameraListener.mIsLeftEye = self.mIsInversed
    def isStereoInversed(self):
        return self.mIsInversed

    def setVisibilityMask(self, leftMask, rightMask):
        self.mRightMask = rightMask
        self.mLeftMask = leftMask
    def getVisibilityMask(self):
        return self.mRightMask, self.mLeftMask

    def getLeftViewport(self):
        return self.mLeftViewport
    def getRightViewport(self):
        return self.mRigmRightViewport

    def saveConfig(self, filename):
        pass
    def loadConfig(self, filename):
        pass

    def updateAllDependentRenderTargets(self, isLeftEye):
        mask = self.mLeftMask if isLeftEye else self.mRightMask
        for rt,isauto in self.mRenderTargetList:
            n = rt.getNumViewports()
            maskVector = [rt.getViewport(ix).getVisibilityMask() for ix in range(n)]
            for ix in range(n): rt.getViewport(ix).setVisibilityMask(maskVector[ix] and mask)
            rt.update()
            for ix in range(n): rt.getViewport(ix).setVisibilityMask(maskVector[ix])
    def chooseDebugPlaneMaterial(self, isLeftEye):
        if self.mDebugPlane:
            if isLeftEye: self.mDebugPlane.setMaterialName(self.mLeftMaterialName)
            else: self.mDebugPlane.setMaterialName(self.mRightMaterialName)

    def updateCamera(self, delta):
        self.mCamera.moveRelative(-delta * ogre.Vector3.UNIT_Z)
        a = 2*math.atan(self.mscreenWidth/(2 * self.mFocalLength * self.mCamera.getAspectRatio()))
        self.mCamera.setFOVy(a)

class StereoCameraListener(ogre.RenderTargetListener):
    def __init__(self, stereoMgr, viewport, isLeftEye):
        self.mOldPos = None #Vector3
        self.mOldOffset = None #Vector2
        self.mOldVisibilityMask = None
        self.mStereoMgr = stereoMgr
        self.mViewport = viewport
        self.mIsLeftEye = isLeftEye
        self.mCamera = None

    def preViewportUpdate(self, evt):
        if evt.source != self.mViewport:
            return
        self.mCamera = self.mViewport.getCamera()
        if not self.mCamera:
            return
        self.mStereoMgr.setCamera(self.mCamera)
        sceneMgr = self.mCamera.getSceneManager()
        self.mOldVisibilityMask = sceneMgr.self.getVisibilityMask()

        if self.mIsLeftEye:
            sceneMgr.setVisibilityMask(self.mStereoMgr.mLeftMask and self.mOldVisibilityMask)
        else:
            sceneMgr.setVisibilityMask(self.mStereoMgr.mRightMask and self.mOldVisibilityMask)

        offset = self.mStereoMgr.getEyesSpacing() * (-0.5 if self.mIsLeftEye else 0.5)

        if not self.mStereoMgr.mIsCustomProjection:
            self.mOldOffset = self.mCamera.getFrustOffset()
            if not self.mStereoMgr.isFocalLengthInfinite():
                self.mCamera.setFrustumOffset(self.mOldOffset - (offset,0))#Vector2
        else:
            if self.mIsLeftEye:
                self.mCamera.setCustomProjectionMatrix(True, self.mstereoMgr.mLeftCustomProjection)
            else:
                self.mCamera.setCustomProjectionMatrix(True, self.mStereoMgr.mRightCustomProjection)

        self.mOldPos = self.mCamera.getPosition()
        pos = self.mOldPos #Vector3
        pos += offset * self.mCamera.getRight()
        self.mCamera.setPosition(pos)
        self.mStereoMgr.updateAllDependentRenderTargets(self.mIsLeftEye)
        self.mStereoMgr.chooseDebugPlaneMaterial(self.mIsLeftEye)

    def postViewportUpdate(self, evt):
        if evt.source != self.mViewport:
            return

        if not self.mStereoMgr.mIsCustomProjection:
            self.mCamera.setFrustumOffset(self.mOldOffset)
        else:
            self.mCamera.setCustomProjectionMatrix(False)

        self.mCamera.setPosition(self.mOldPos)
        self.mCamera.getSceneManager().setVisibilityMask(self.mOldVisibilityMask)


class DeviceLostListener(ogre.RenderSystem.Listener):
    def __init__(self, stereoMgr):
        self.mStereoMgr = stereoMgr

    def eventOccurred(self, eventName, parameters):
        if eventName=="DeviceRestored" and self.mStereoMgr.mCompositorInstance:
            self.mStereoMgr.shutdownListeners()
            leftViewport = self.mStereoMgr.mCompositorInstance.getRenderTarget("Stereo/Left").getViewport(0)
            rightViewport = self.mStereoMgr.mCompositorInstance.getRenderTarget("Stereo/Right").getViewport(0)
            self.mStereoMgr.initListeners(leftViewport, rightViewport)