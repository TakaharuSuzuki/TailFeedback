import numpy as np
from random import randint, uniform, random, shuffle
from math import ceil, sqrt, floor
import time
import OgreRenderer as OgreRenderer
from OgreRenderer import HandStimulus, Disc, Block, Text
import SigTools
from AppTools.Boxes import box
from AppTools.Displays import fullscreen
from AppTools.StateMonitors import addstatemonitor, addphasemonitor
#from AppTools.Shapes import Disc

class BciApplication(BciGenericApplication):

    def Description(self):
        return "Hand animation."

    #############################################################
    def Construct(self):
        #See here for already defined params and states http://bci2000.org/wiki/index.php/Contributions:BCPy2000#CurrentBlock
        #See further details http://bci2000.org/wiki/index.php/Technical_Reference:Parameter_Definition
        params = [
            "PythonApp:Design   list    GoCueText=      1 Imagery % % % // Text for cues. Defines N targets",
            "PythonApp:Design   float   MaxThresh=  2.0 % % %       // Maximum value for animations/movements",
            "PythonApp:Design   float   MinThresh=  -2.0 % % %       // Minimum value for animations/movements",
            ]
        states = [
            #===================================================================
            "Baseline 1 0 0 0", #Sometimes useful for Normalizer.
            "GoCue 1 0 0 0",
            "Task 1 0 0 0",
            "TriggerJudge 1 0 0 0",
            "TargetClass 1 0 0 0", #Sometimes useful for Normalizer.
            "Default 1 0 0 0", #0 not default, 1 default
        ]        
        return params,states

    #############################################################
    def Preflight(self, sigprops):
        pass
        #TODO: Check parameters

    #############################################################
    def Initialize(self, indim, outdim):
        #=======================================================================
        # Make a few variables easier to access, especially those accessed every packet.
        #=======================================================================
        self.max_thresh = self.params['MaxThresh'].val
        self.min_thresh = self.params['MinThresh'].val
        self.xpos = (-23.0, -8.0)
        self.ypos = (3.0, 18.0)
        self.fbpos = (8, -50, -56.5)
        self.trigger = False
        self.triggerSig = 0
        
        #=======================================================================
        # Screen
        #=======================================================================
        self.screen.color = (0,0,0) #let's have a black background
        self.scrw,self.scrh = self.screen.size #Get the screen dimensions.
        self.screen.app.camera.position = (0, 0, 0)
        self.screen.app.camera.lookAt ((0, -35, -40))
        self.screen.app.camera.nearClipDistance = 1
        import ogre.renderer.OGRE as ogre
        self.screen.app.camera.setFOVy(ogre.Degree(21.2))
        
        #=======================================================================
        # Register the cue text stimuli.
        #=======================================================================
        self.stimulus('cue', z=5, stim=VisualStimuli.Text(text='?', position=(400,400,0), anchor='center', color=(1,1,1), font_size=50, on=True))
        self.stimuli['cue'].on = False
              
        #=======================================================================
        # Create the feedback
        #=======================================================================
        self.feedback = OgreRenderer.TailStimulus()
        self.vx, self.vy = -8, 18
        self.feedback.inverseKinematics(True, True, self.vx, self.vy, 0)
        self.screen.app.camera.lookAt ((0, 0, -1))
        self.fbpos = (10, -13, -45)
        self.screen.app.camera.setFOVy(ogre.Degree(27.0))
        self.feedback.node.setPosition(self.fbpos)
        self.feedback.node.setVisible(True)
        
        #=======================================================================
        # State monitors for debugging.
        #=======================================================================
        if int(self.params['ShowSignalTime']):
            # turn on state monitors if the packet clock is also turned on
            addstatemonitor(self, 'Running', showtime=True)
            addstatemonitor(self, 'CurrentBlock')
            addstatemonitor(self, 'CurrentTrial')
            addstatemonitor(self, 'TargetClass')
            addphasemonitor(self, 'phase', showtime=True)
            addstatemonitor(self, 'ShouldAnim')
            addstatemonitor(self, 'IsAnim')
            addstatemonitor(self, 'AnimPcnt')

            m = addstatemonitor(self, 'fs_reg')
            m.func = lambda x: '% 6.1fHz' % x._regfs.get('SamplesPerSecond', 0)
            m.pargs = (self,)
            m = addstatemonitor(self, 'fs_avg')
            m.func = lambda x: '% 6.1fHz' % x.estimated.get('SamplesPerSecond',{}).get('global', 0)
            m.pargs = (self,)
            m = addstatemonitor(self, 'fs_run')
            m.func = lambda x: '% 6.1fHz' % x.estimated.get('SamplesPerSecond',{}).get('running', 0)
            m.pargs = (self,)
            m = addstatemonitor(self, 'fr_run')
            m.func = lambda x: '% 6.1fHz' % x.estimated.get('FramesPerSecond',{}).get('running', 0)
            m.pargs = (self,)
        
    #############################################################
    def Halt(self):
        pass

    #############################################################
    def StartRun(self):
        self.forget('task_start') #Initialize this timekeeper at t=0.
        self.forget('range_ok')

    #############################################################
    def StopRun(self):
        pass
        
    #############################################################
    def Phases(self):
        # define phase machine using calls to self.phase and self.design
        self.phase(name='preRun', next='triggerJudge', duration=1000.0)
        if not self.trigger:
            self.phase(name='triggerJudge', next='triggerJudge', duration=1000.0)
        elif self.trigger:
            self.phase(name='triggerJudge', next='relaxcue', duration=1000.0)
            self.phase(name='relaxcue', next='baseline', duration=1000.0)
            self.phase(name='baseline', next='gocue', duration=4000.0)
            self.phase(name='gocue', next='task', duration=1000.0)
            self.phase(name='task', next='stopcue',duration=6000.0)
            self.phase(name='stopcue', next='triggerJudge', duration=1000.0)
        self.design(start='preRun', new_trial='intertrial') #It's possible to add a stop phase but so far I have been unsuccessful.

    #############################################################
    def Transition(self, phase):
        # Phase information is recorded in a state called PresentationPhase
        # but sometimes it is necessary to have more direct access, 
        # especially for the Normalizer.
        self.states['Baseline'] = int(phase in ['baseline'])
        self.states['GoCue'] = int(phase in ['gocue'])
        self.states['Task'] = int(phase in ['task'])
        self.states['TriggerJudge'] = int(phase in ['triggerJudge'])
        
        if phase == 'intertrial':
            pass
        elif phase == 'relaxcue':
            self.stimuli['cue'].text = "Relax"
        elif phase == 'baseline':
            pass
        elif phase == 'gocue':
            self.stimuli['cue'].text = self.params['GoCueText'][0]          #Change the cue text to the target text.
            self.states['TargetClass'] = 1                                  #Record that the target is now on the screen.
        elif phase == 'task':                                               #Reset variables relevant for task monitoring.
            pass
        elif phase == 'stopcue':
            self.stimuli['cue'].text = "Relax"
            self.states['TargetClass'] = 0
            self.trigger = False
        elif phase == 'triggerJudge':
            if self.triggerSig:
                self.trigger = True
                self.triggerSig = 0
            elif not self.triggerSig:
                self.trigger = False

        self.stimuli['cue'].on = phase in ['gocue', 'stopcue','relaxcue']
        
    #############################################################
    def Process(self, sig):
        #Process is called on every packet/block. This is used for real-time feedback.
        if self.in_phase('task'):
			x = sig[0,:].mean(axis=1)
			y = sig[1,:].mean(axis=1)
			x = x.A.ravel()[0]
			y = y.A.ravel()[0]
			x = np.clip( x, self.min_thresh, self.max_thresh )
			y = np.clip( y, self.min_thresh, self.max_thresh ) # signals should be within the range
			self.vx = x*(self.xpos[1]-self.xpos[0])/(self.max_thresh-self.min_thresh)+self.xpos[0]-(self.xpos[1]-self.xpos[0])/(self.max_thresh-self.min_thresh)*self.min_thresh
			self.vy = y*(self.ypos[1]-self.ypos[0])/(self.max_thresh-self.min_thresh)+self.ypos[0]-(self.ypos[1]-self.ypos[0])/(self.max_thresh-self.min_thresh)*self.min_thresh

        # tailWithoutAnimation
        if self.in_phase('task'):
            self.feedback.inverseKinematics(True, False, self.vx, self.vy, 0.12)
            self.states['Default'] = 0
        elif not self.in_phase('task') and not self.states['Default']:
            self.feedback.inverseKinematics(True, True, self.vx, self.vy, 1)
            self.states['Default'] = 1

        # trigger
        self.triggerSig = sig[0,:].mean(axis=1)
        if self.triggerSig > 1.0:
            self.triggerSig = 1
        elif self.triggerSig < 1.0:
            self.triggerSig = 0
        print self.triggerSig
		
    #############################################################
    def Frame(self, phase):
        # update stimulus parameters if they need to be animated on a frame-by-frame basis
        pass

    #############################################################
    def Event(self, phase, event):
        pass

#################################################################
#################################################################