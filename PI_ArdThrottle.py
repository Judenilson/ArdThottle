# Tem q instalar a biblioteca pyserial https://pypi.org/project/pyserial/
# in linux: sudo apt-get install python-pyserial
import serial
import sys
import glob
import serial.tools.list_ports
import json
# X-plane includes
from XPLMDefs import *
from XPLMProcessing import *
from XPLMDataAccess import *
from XPLMUtilities import *
from XPLMPlanes import *
from XPLMNavigation import *
from SandyBarbourUtilities import *
from PythonScriptMessaging import *
from XPLMPlugin import *
from XPLMMenus import *
from XPWidgetDefs import *
from XPWidgets import *
from XPStandardWidgets import *

class PythonInterface:
	def XPluginStart(self):
		self.Name = "ArdTHROTTLE"
		self.Sig =  "JUD.Python.ArdTHROTTLE"
		self.Desc = "Conecta o THROTTLE Arduino ao Simulador"
		self.MsgA = "Ard THROTTLE"
		self.MsgB = ""
		
		self.LEDS = "LD0000000,"
		self.LEDSLastState = "LD0000001,"		
		self.data = [0,0,0,0,0,0]
		self.Potenciometros = {"A":0.0,"B":0.0,"C":0.0,"D":0.0,"E":0.0,"F":0.0}
		self.throttle = [0.0,0.0]
		self.prop = [0.0,0.0,0.0]
		
		self.flapsPositions = []
		self.flapsMedia = []
				
		self.portas = []
		self.ardSerial = serial.Serial()
		self.connected = False		
		ports = serial.tools.list_ports.comports()
		for port, desc, hwid in sorted(ports):
			self.portas.append(port)
		self.qtdPortas = len(self.portas)		
		self.portasWidgets=[]

		self.configs = {'portaCOM':'_',
						'aircraft':'',
						'qtdFlaps':3,
						'stepSpeedBMin':200,
						'stepSpeedBMax':750,
						'stepThrottleLMin':200,
						'stepThrottleLMax':750,
						'stepThrottleRMin':200,
						'stepThrottleRMax':750,
						'stepPropellerMin':200,
						'stepPropellerMax':750,
						'stepMixtureMin':200,
						'stepMixtureMax':750,
						'stepFlapMin':200,
						'stepFlapMax':750,										
						'stepPropellerAdjustMin':105.0,
						'stepPropellerAdjustMax':230.0,
						}

		self.openConfig()
		self.configflaps()
		self.calibarProp = False
		self.calibrar = False
		self.ziboDRef = False
		self.tolissDRef = False
		self.ka350DRef = False
		
		self.aircraftType = ['zibo']

		self.DataRefSpeedBrake = XPLMFindDataRef("sim/cockpit2/controls/speedbrake_ratio")
		self.DataRefThrottle = XPLMFindDataRef("sim/cockpit2/engine/actuators/throttle_ratio")


		self.DataRefMixtureAll = XPLMFindDataRef("sim/cockpit2/engine/actuators/mixture_ratio_all")
		self.DataRefPropeller = XPLMFindDataRef("sim/cockpit2/engine/actuators/prop_rotation_speed_rad_sec") #float array[8]
		self.DataRefPropellerAll = XPLMFindDataRef("sim/cockpit2/engine/actuators/prop_rotation_speed_rad_sec_all") #105.0 - 230.0 #99.0 - 146.0
		self.DataRefFlap = XPLMFindDataRef("sim/cockpit2/controls/flap_ratio")

		self.DataRefAutoTh = XPLMFindDataRef("sim/cockpit2/autopilot/autothrottle_enabled") 

		self.DataRefGear1def = XPLMFindDataRef("sim/flightmodel/movingparts/gear1def")
		self.DataRefGear2def = XPLMFindDataRef("sim/flightmodel/movingparts/gear2def")
		self.DataRefGear3def = XPLMFindDataRef("sim/flightmodel/movingparts/gear3def")
		
		self.DataRefParkingBrake = XPLMFindDataRef("sim/cockpit2/controls/parking_brake_ratio")

		self.Floop = self.FloopCallback
		XPLMRegisterFlightLoopCallback(self, self.Floop, 1.0, 0)

		# Menu / About
		self.Mmenu = self.mainMenuCB
		self.flagConfigWindow = False
		self.timeCloseConfigWindow = 0
		self.configWindow = False
		self.calibrarWindow = False
		self.aboutWindow = False
		self.mPluginItem = XPLMAppendMenuItem(XPLMFindPluginsMenu(), 'ArdTHROTTLE', 0, 1)
		self.mMain       = XPLMCreateMenu(self, 'ArdTHROTTLE', XPLMFindPluginsMenu(), self.mPluginItem, self.Mmenu, 0)

		# Menu Items
		XPLMAppendMenuItem(self.mMain, 'Conectar', 1, 1)
		XPLMAppendMenuItem(self.mMain, 'Calibrar', 2, 1)
		XPLMAppendMenuItem(self.mMain, 'Sobre', 3, 1)

		return self.Name, self.Sig, self.Desc

	def ka350DataRef(self):		
		# Data Refs do Airfoilabs K350
		self.KA350DataRefProp = XPLMFindDataRef("KA350/systems/throttle/propLeverPosition") #array 3 dados [L, R, o maior L ou R]
		return 1

	def TolissDataRef(self):		
		# Data Refs do TOLISS
		self.TOLISSDataRefThrottle = XPLMFindDataRef("AirbusFBW/throttle_input") #array 5 dados [L, R, Mandar Nada, Mandar Nada, Mandar Nada]
		return 1

	def ZIBODataREF(self):
		# Data Refs do ZIBO
		self.ZIBODataRefFlap = XPLMFindDataRef("laminar/B738/flt_ctrls/flap_lever")
		self.ZIBODataRefSpeedBrake = XPLMFindDataRef("laminar/B738/flt_ctrls/speedbrake_lever")
		self.ZIBODataRefSpeedBrakeStop = XPLMFindDataRef("laminar/B738/flt_ctrls/speedbrake_lever_stop")
		self.ziboDRef = True
		return 1

	def mainMenuCB(self, menuRef, menuItem):
		if menuItem == 1:
			if not self.configWindow:
				self.createConfigWindow()
				self.configWindow = True
			elif (not XPIsWidgetVisible(self.configWindowWidget)):
				XPShowWidget(self.configWindowWidget)

		elif menuItem == 2:
			if not self.calibrarWindow:
				self.createCalibrarWindow()
			elif not XPIsWidgetVisible(self.calibrarWindowWidget):
				XPShowWidget(self.calibrarWindowWidget)

		elif menuItem == 3:
			if not self.aboutWindow:
				self.createAboutWindow()
			elif not XPIsWidgetVisible(self.aboutWindowWidget):
				XPShowWidget(self.aboutWindowWidget)

	def createConfigWindow(self):
		# (left, top, bottom, right) lefto, esquerda, base, direita - A origem e no canto inferior esquerdo!
		left = 240
		top = 540
		right = left + 160
		bottom = top - 188 - (20 * (self.qtdPortas))
		leftRst = left + 20 #com margem
		topRst = top
		rightRst = right - 20 #com margem
		bottomRst = bottom
		Titulo = "ArdT Conectar"
		separador = '_________________________'

		# criando a janela principal
		self.configWindowWidget = XPCreateWidget(left, top, right, bottom, 1, Titulo, 1, 0, xpWidgetClass_MainWindow)
		window = self.configWindowWidget
		XPSetWidgetProperty(window, xpProperty_MainWindowHasCloseBoxes, 1) # botao de fechar a janela, simples assim hehe

		# aviso
		left += 20		
		right -= 20
		top -= 20
		bottom = top - 15
		XPCreateWidget(left-2, top, right, bottom, 1, '  Selecione a Serial', 0, window, xpWidgetClass_Caption)
		top -= 15
		bottom = top - 15
		XPCreateWidget(left, top, right, bottom, 1,   '   que esta ligada', 0, window, xpWidgetClass_Caption)
		top -= 15
		bottom = top - 15
		XPCreateWidget(left, top, right, bottom, 1,   '   no seu Throttle', 0, window, xpWidgetClass_Caption)

		top -= 15
		bottom = top - 5
		self.separatorA = XPCreateWidget(left-20, top, right+20, bottom, 1, separador, 0, window, xpWidgetClass_Caption)
		
		# radios botoes das portas seriais
		self.portasWidgets = []
		for i in range(self.qtdPortas):
			top -= 20
			bottom = top - 20
			right = left + 5
			self.portasWidgets.append(XPCreateWidget(left, top, right, bottom, 1, '', 0, window, xpWidgetClass_Button))
			left = right + 5
			right = rightRst
			XPCreateWidget(left, top, right, bottom, 1, self.portas[i], 0, window, xpWidgetClass_Caption)
			left = leftRst

		for i in range(self.qtdPortas):
			XPSetWidgetProperty(self.portasWidgets[i], xpProperty_ButtonType, xpRadioButton)
			XPSetWidgetProperty(self.portasWidgets[i], xpProperty_ButtonBehavior, xpButtonBehaviorCheckBox)
			XPSetWidgetProperty(self.portasWidgets[i], xpProperty_ButtonState, int(self.configs['portaCOM'] == self.portas[i]))

		top -= 15
		bottom = top - 5
		self.separatorB = XPCreateWidget(left-20, top, right+20, bottom, 1, separador, 0, window, xpWidgetClass_Caption)

		top -= 20
		bottom = top - 20
		self.connectArduino = XPCreateWidget(left, top, right, bottom, 1, "--> CONECTAR <--", 0, window, xpWidgetClass_Button)
		XPSetWidgetProperty(self.connectArduino, xpProperty_ButtonType, xpPushButton)

		top -= 20
		bottom = top - 40
		if self.connected:
			XPSetWidgetProperty (self.connectArduino , xpProperty_Enabled, 0)
			self.textConnect = XPCreateWidget(left, top, right, bottom, 1, "    Conectado :D", 0, window, xpWidgetClass_Caption)
		else:
			XPSetWidgetProperty (self.connectArduino , xpProperty_Enabled, 1)
			self.textConnect = XPCreateWidget(left, top, right, bottom, 1, "   Desconectado :(", 0, window, xpWidgetClass_Caption)
			
		top -= 35
		bottom = top - 5
		self.separatorC = XPCreateWidget(left-20, top, right+20, bottom, 1, separador, 0, window, xpWidgetClass_Caption)

		# Visit site Button
		top -= 15
		bottom = top - 15
		self.homePage = XPCreateWidget(left, top, right, bottom, 1, "DESENVOLVEDOR", 0, window, xpWidgetClass_Button)
		XPSetWidgetProperty(self.homePage, xpProperty_ButtonType, xpPushButton)

		# Register our widget handler
		self.configWindowHandleCB = self.configWindowHandle
		XPAddWidgetCallback(self, window, self.configWindowHandleCB)

		self.configWindow = window

	def configWindowHandle(self, inMessage, inWidget, inParam1, inParam2):
		if (inMessage == xpMessage_CloseButtonPushed):
			if self.configWindow:
				XPDestroyWidget(self, self.configWindowWidget, 1)
				self.configWindow = False
			return 1

		if inMessage == xpMsg_ButtonStateChanged and inParam1 in self.portasWidgets:
			if inParam2:
				for i in self.portasWidgets:
					if i != inParam1:
						XPSetWidgetProperty(i, xpProperty_ButtonState, 0)
			else:
				XPSetWidgetProperty(inParam1, xpProperty_ButtonState, 1)
			return 1

		# Lidar com qualquer aperto de botao
		if (inMessage == xpMsg_PushButtonPressed):

			if (inParam1 == self.homePage):
				from webbrowser import open_new
				open_new('http://judenilson.com.br/');
				return 1

			if (inParam1 == self.connectArduino):				
				for i in range(self.qtdPortas):
					if XPGetWidgetProperty(self.portasWidgets[i], xpProperty_ButtonState, None):
						self.configs['portaCOM'] = self.portas[i]
					
				if self.connectSerial():
					XPSetWidgetProperty (self.connectArduino , xpProperty_Enabled, 0)
					XPSetWidgetDescriptor(self.textConnect, self.MsgA)
					self.flagConfigWindow = True
				else:					
					XPSetWidgetDescriptor(self.textConnect, self.MsgA)
				return 1

		return 0

	def createCalibrarWindow(self):
		# (left, top, bottom, right) left0, esquerda, base, direita - A origem e no canto inferior esquerdo!
		left = 420
		top = 540
		right = left + 160
		bottom = top - 460
		leftRst = left + 20 #com margem
		topRst = top
		rightRst = right - 20 #com margem
		bottomRst = bottom
		Titulo = "ArdT Calibrar"
		separador = '_________________________'

		# criando a janela principal
		self.calibrarWindowWidget = XPCreateWidget(left, top, right, bottom, 1, Titulo, 1, 0, xpWidgetClass_MainWindow)
		calWindow = self.calibrarWindowWidget
		XPSetWidgetProperty(calWindow, xpProperty_MainWindowHasCloseBoxes, 1) # botao de fechar a janela, simples assim hehe

		left += 20		
		right -= 20
		top -= 20
		bottom = top - 15
		XPCreateWidget(left, top, right, bottom, 1, 'Aperte em Calibrar', 0, calWindow, xpWidgetClass_Caption)
		top -= 15
		bottom = top - 15
		XPCreateWidget(left, top, right, bottom, 1, 'mova os controles', 0, calWindow, xpWidgetClass_Caption)
		top -= 15
		bottom = top - 15
		XPCreateWidget(left, top, right, bottom, 1, '  salve os ajustes', 0, calWindow, xpWidgetClass_Caption)

		top -= 15
		bottom = top - 5
		XPCreateWidget(left-20, top, right+20, bottom, 1, separador, 0, calWindow, xpWidgetClass_Caption)

		top -= 15
		bottom = top - 20
		self.calibrarButton = XPCreateWidget(left, top, right, bottom, 1, "--> CALIBRAR <--", 0, calWindow, xpWidgetClass_Button)
		XPSetWidgetProperty(self.calibrarButton, xpProperty_ButtonType, xpPushButton)
		
		top -= 15
		bottom = top - 5
		XPCreateWidget(left-20, top, right+20, bottom, 1, separador, 0, calWindow, xpWidgetClass_Caption)
										
		top -= 15
		bottom = top - 20
		self.joySpeedBrake = XPCreateWidget(left, top, right, bottom, 1, '1 - ['+str(self.configs['stepSpeedBMin'])+'/'+str(self.configs['stepSpeedBMax'])+'] - '+str(self.data[0]), 0, calWindow, xpWidgetClass_Caption)
		top -= 20
		bottom = top - 20
		self.joyThrottleL = XPCreateWidget(left, top, right, bottom, 1, '2 - ['+str(self.configs['stepThrottleLMin'])+'/'+str(self.configs['stepThrottleLMax'])+'] - '+str(self.data[1]), 0, calWindow, xpWidgetClass_Caption)
		top -= 20
		bottom = top - 20
		self.joyThrottleR = XPCreateWidget(left, top, right, bottom, 1, '3 - ['+str(self.configs['stepThrottleRMin'])+'/'+str(self.configs['stepThrottleRMax'])+'] - '+str(self.data[2]), 0, calWindow, xpWidgetClass_Caption)
		top -= 20
		bottom = top - 20
		self.joyPropeller = XPCreateWidget(left, top, right, bottom, 1, '4 - ['+str(self.configs['stepPropellerMin'])+'/'+str(self.configs['stepPropellerMax'])+'] - '+str(self.data[3]), 0, calWindow, xpWidgetClass_Caption)
		top -= 20
		bottom = top - 20
		self.joyMixture = XPCreateWidget(left, top, right, bottom, 1, '5 - ['+str(self.configs['stepPropellerMin'])+'/'+str(self.configs['stepPropellerMax'])+'] - '+str(self.data[4]), 0, calWindow, xpWidgetClass_Caption)
		top -= 20
		bottom = top - 20
		self.joyFlaps = XPCreateWidget(left, top, right, bottom, 1, '6 - ['+str(self.configs['stepFlapMin'])+'/'+str(self.configs['stepFlapMax'])+'] - '+str(self.data[5]), 0, calWindow, xpWidgetClass_Caption)
		
		top -= 15
		bottom = top - 5
		XPCreateWidget(left-20, top, right+20, bottom, 1, separador, 0, calWindow, xpWidgetClass_Caption)

		top -= 15
		bottom = top - 20
		self.calibrarPropButton = XPCreateWidget(left, top, right, bottom, 1, "Ajuste de Propeller", 0, calWindow, xpWidgetClass_Button)
		XPSetWidgetProperty(self.calibrarPropButton, xpProperty_ButtonType, xpPushButton)

		top -= 20
		bottom = top - 20
		self.textPropAdjust = XPCreateWidget(left, top, right, bottom, 1, "Min " + str(int(self.configs['stepPropellerAdjustMin'])) + ' | Max ' + str(int(self.configs['stepPropellerAdjustMax'])), 0, calWindow, xpWidgetClass_Caption)

		top -= 15
		bottom = top - 5
		XPCreateWidget(left-20, top, right+20, bottom, 1, separador, 0, calWindow, xpWidgetClass_Caption)

		top -= 20
		bottom = top - 20
		right = left + 5
		self.airplaneWidgets = XPCreateWidget(left, top, right, bottom, 1, '', 0, calWindow, xpWidgetClass_Button)
		left = right + 5
		right = rightRst
		XPCreateWidget(left, top, right, bottom, 1, 'Marque para ZIBO', 0, calWindow, xpWidgetClass_Caption)
		XPSetWidgetProperty(self.airplaneWidgets, xpProperty_ButtonType, xpRadioButton)
		XPSetWidgetProperty(self.airplaneWidgets, xpProperty_ButtonBehavior, xpButtonBehaviorCheckBox)
		XPSetWidgetProperty(self.airplaneWidgets, xpProperty_ButtonState, 0)
		left = leftRst		

		top -= 20
		bottom = top - 20
		right = left + 5
		self.airplaneWidgetsToliss = XPCreateWidget(left, top, right, bottom, 1, '', 0, calWindow, xpWidgetClass_Button)
		left = right + 5
		right = rightRst
		XPCreateWidget(left, top, right, bottom, 1, 'Marque para TOLISS', 0, calWindow, xpWidgetClass_Caption)
		XPSetWidgetProperty(self.airplaneWidgetsToliss, xpProperty_ButtonType, xpRadioButton)
		XPSetWidgetProperty(self.airplaneWidgetsToliss, xpProperty_ButtonBehavior, xpButtonBehaviorCheckBox)
		XPSetWidgetProperty(self.airplaneWidgetsToliss, xpProperty_ButtonState, 0)
		left = leftRst			

		top -= 20
		bottom = top - 20
		right = left + 5
		self.airplaneWidgetsKA350 = XPCreateWidget(left, top, right, bottom, 1, '', 0, calWindow, xpWidgetClass_Button)
		left = right + 5
		right = rightRst
		XPCreateWidget(left, top, right, bottom, 1, 'Marque para KA350', 0, calWindow, xpWidgetClass_Caption)
		XPSetWidgetProperty(self.airplaneWidgetsKA350, xpProperty_ButtonType, xpRadioButton)
		XPSetWidgetProperty(self.airplaneWidgetsKA350, xpProperty_ButtonBehavior, xpButtonBehaviorCheckBox)
		XPSetWidgetProperty(self.airplaneWidgetsKA350, xpProperty_ButtonState, 0)
		left = leftRst	

		top -= 15
		bottom = top - 5
		XPCreateWidget(left-20, top, right+20, bottom, 1, separador, 0, calWindow, xpWidgetClass_Caption)

		top -= 15
		bottom = top - 20
		self.textflap = XPCreateWidget(left, top, right, bottom, 1, " Posicoes FLAPS %d" % (self.configs['qtdFlaps']), 0, calWindow, xpWidgetClass_Caption)

		top -= 20
		bottom = top - 20
		self.flapSlider = XPCreateWidget(left, top, right, bottom, 1, '', 0, calWindow, xpWidgetClass_ScrollBar)
		XPSetWidgetProperty(self.flapSlider, xpProperty_ScrollBarType, xpScrollBarTypeSlider)
		XPSetWidgetProperty(self.flapSlider, xpProperty_ScrollBarMin, 2)
		XPSetWidgetProperty(self.flapSlider, xpProperty_ScrollBarMax, 12)
		XPSetWidgetProperty(self.flapSlider, xpProperty_ScrollBarPageAmount, 1)

		XPSetWidgetProperty(self.flapSlider, xpProperty_ScrollBarSliderPosition, self.configs['qtdFlaps'])

		top -= 15
		bottom = top - 5
		XPCreateWidget(left-20, top, right+20, bottom, 1, separador, 0, calWindow, xpWidgetClass_Caption)

		top -= 15
		bottom = top - 20
		self.save = XPCreateWidget(left, top, right, bottom, 1, "--> SALVAR <--", 0, calWindow, xpWidgetClass_Button)
		XPSetWidgetProperty(self.save, xpProperty_ButtonType, xpPushButton)

		top -= 20
		bottom = top - 20
		self.textSave = XPCreateWidget(left, top, right, bottom, 1, "", 0, calWindow, xpWidgetClass_Caption)

		# Register our widget handler
		self.calibrarWindowHandleCB = self.calibrarWindowHandle
		XPAddWidgetCallback(self, calWindow, self.calibrarWindowHandleCB)

		self.calibrarWindow = calWindow

	def calibrarWindowHandle(self, inMessage, inWidget, inParam1, inParam2):
		if (inMessage == xpMessage_CloseButtonPushed):
			if self.calibrarWindow:
				XPDestroyWidget(self, self.calibrarWindowWidget, 1)
				self.calibrarWindow = False
				self.calibrar = False
			return 1

		if inMessage == xpMsg_ButtonStateChanged and inParam1 == self.airplaneWidgets:
			if inParam2:
				XPSetWidgetProperty(self.airplaneWidgets, xpProperty_ButtonState, 1)
				XPSetWidgetProperty(self.airplaneWidgetsToliss, xpProperty_ButtonState, 0)				
				XPSetWidgetProperty(self.airplaneWidgetsKA350, xpProperty_ButtonState, 0)
				XPSetWidgetProperty(self.flapSlider, xpProperty_ScrollBarSliderPosition, 9)
				XPSetWidgetDescriptor(self.textflap, " Posicoes FLAPS 9")
			else:
				XPSetWidgetProperty(self.airplaneWidgets, xpProperty_ButtonState, 0)
			return 1

		if inMessage == xpMsg_ButtonStateChanged and inParam1 == self.airplaneWidgetsToliss:
			if inParam2:
				XPSetWidgetProperty(self.airplaneWidgets, xpProperty_ButtonState, 0)
				XPSetWidgetProperty(self.airplaneWidgetsToliss, xpProperty_ButtonState, 1)				
				XPSetWidgetProperty(self.airplaneWidgetsKA350, xpProperty_ButtonState, 0)
				XPSetWidgetProperty(self.flapSlider, xpProperty_ScrollBarSliderPosition, 5)				
				XPSetWidgetDescriptor(self.textflap, " Posicoes FLAPS 5")
			else:
				XPSetWidgetProperty(self.airplaneWidgetsToliss, xpProperty_ButtonState, 0)
			return 1

		if inMessage == xpMsg_ButtonStateChanged and inParam1 == self.airplaneWidgetsKA350:
			if inParam2:
				XPSetWidgetProperty(self.airplaneWidgets, xpProperty_ButtonState, 0)
				XPSetWidgetProperty(self.airplaneWidgetsToliss, xpProperty_ButtonState, 0)				
				XPSetWidgetProperty(self.airplaneWidgetsKA350, xpProperty_ButtonState, 1)
				XPSetWidgetProperty(self.flapSlider, xpProperty_ScrollBarSliderPosition, 5)				
				XPSetWidgetDescriptor(self.textflap, " Posicoes FLAPS 5")
			else:
				XPSetWidgetProperty(self.airplaneWidgetsKA350, xpProperty_ButtonState, 0)
			return 1

		if inMessage == xpMsg_ScrollBarSliderPositionChanged and inParam1 == self.flapSlider:
			val = XPGetWidgetProperty(self.flapSlider, xpProperty_ScrollBarSliderPosition, None)
			XPSetWidgetDescriptor(self.textflap, " Posicoes FLAPS %d" % (val))
			return 1

		# Lidar com qualquer aperto de botao
		if (inMessage == xpMsg_PushButtonPressed):

			if (inParam1 == self.calibrarButton):
				XPSetWidgetDescriptor(self.calibrarButton, "Calibrando...")
				XPSetWidgetDescriptor(self.textSave, "")
				XPSetWidgetProperty (self.calibrarButton , xpProperty_Enabled, 0)
				self.configs['stepSpeedBMin'] = self.data[0]
				self.configs['stepSpeedBMax'] = self.data[0]+1
				self.configs['stepThrottleLMin'] = self.data[1]
				self.configs['stepThrottleLMax'] = self.data[1]+1
				self.configs['stepThrottleRMin'] = self.data[2]
				self.configs['stepThrottleRMax'] = self.data[2]+1
				self.configs['stepPropellerMin'] = self.data[3]
				self.configs['stepPropellerMax'] = self.data[3]+1
				self.configs['stepMixtureMin'] = self.data[4]
				self.configs['stepMixtureMax'] = self.data[4]+1
				self.configs['stepFlapMin'] = self.data[5]
				self.configs['stepFlapMax'] = self.data[5]+1
				self.calibrar = True
				return 1

			if (inParam1 == self.calibrarPropButton):
				XPSetWidgetDescriptor(self.calibrarPropButton, "Mova no aviao!")
				XPSetWidgetProperty (self.calibrarPropButton, xpProperty_Enabled, 0)
				prop = XPLMGetDataf(self.DataRefPropellerAll)
				self.configs['stepPropellerAdjustMin'] = prop
				self.configs['stepPropellerAdjustMax'] = prop

				self.calibarProp = True
				return 1

			if (inParam1 == self.save):				
				if XPGetWidgetProperty(self.airplaneWidgets, xpProperty_ButtonState, None):
					self.configs['aircraft'] = self.aircraftType[0]
					self.ziboDRef = True
					self.ZIBODataREF()					
				else:
					self.ziboDRef = False

					if XPGetWidgetProperty(self.airplaneWidgetsToliss, xpProperty_ButtonState, None):
						self.configs['aircraft'] = self.aircraftType[0]
						self.tolissDRef = True
						self.TolissDataRef()					
					else:
						self.tolissDRef = False

						if XPGetWidgetProperty(self.airplaneWidgetsKA350, xpProperty_ButtonState, None):
							self.configs['aircraft'] = self.aircraftType[0]
							self.ka350DRef = True
							self.ka350DataRef()				
						else:
							self.ka350DRef = False
							self.configs['aircraft'] = ''

				self.configs['qtdFlaps'] = XPGetWidgetProperty(self.flapSlider, xpProperty_ScrollBarSliderPosition, None)

				if self.saveConfig():
					self.configflaps()
					self.calibrar = False
					self.calibarProp = False
					XPSetWidgetDescriptor(self.calibrarButton, "--> CALIBRAR <--")
					XPSetWidgetDescriptor(self.calibrarPropButton, "Ajuste de Propeller")
					XPSetWidgetProperty (self.calibrarButton, xpProperty_Enabled, 1)
					XPSetWidgetProperty (self.calibrarPropButton, xpProperty_Enabled, 1)
					XPSetWidgetDescriptor(self.textSave, self.MsgB)
				else:					
					XPSetWidgetDescriptor(self.textSave, self.MsgB)
				return 1

		return 0

	def createAboutWindow(self):
		left = 100
		w = 440
		top = 600
		h = 100
		right = left + w
		bottom = top - h
		aboutTitle = "-- Sobre --"
		mensagem = ['Produto desenvolvido por Judenilson Araujo sob licenca GNU/GPLv2.',
								'Sinta-se livre para fazer o que quiser, com o software e o hardware.',
								'Apenas solicito que voce tambem divulgue as melhorias e updates.',
								'                                           Grande Abraco e divirta-se...']

		self.aboutWindow = True
		self.aboutWindowWidget = XPCreateWidget(left, top, right, bottom, 1, aboutTitle, 1, 0, xpWidgetClass_MainWindow)
		about = self.aboutWindowWidget
		XPSetWidgetProperty(about, xpProperty_MainWindowType,  xpMainWindowStyle_Translucent)
		XPSetWidgetProperty(about, xpProperty_MainWindowHasCloseBoxes, 1)
		left += 20
		top -= 20

		self.cap = []
		for i in range(4):
			self.cap.append(XPCreateWidget(left, top-(15*i), right, top-20-(20*i), 1, mensagem[i], 0, about, xpWidgetClass_Caption))
			XPSetWidgetProperty(self.cap[i], xpProperty_CaptionLit, 1)

		self.aboutWindowHandleCB = self.aboutWindowHandle
		XPAddWidgetCallback(self, about, self.aboutWindowHandleCB)

		self.aboutWindow = about

	def aboutWindowHandle(self, inMessage, inWidget, inParam1, inParam2):
		if inMessage == xpMessage_CloseButtonPushed:
			if self.aboutWindow:
				XPHideWidget(self.aboutWindowWidget)
				return 1
		return 0

	def connectSerial(self):
		try:
			self.ardSerial.baudrate = 115200
			self.ardSerial.port = self.configs['portaCOM']
			self.ardSerial.open()
			if(self.ardSerial.isOpen()):
				self.connected = True
				self.MsgA = "    Conectado :D"			
				self.saveConfig()
				return 1
		except serial.SerialException as e:
			if self.configs['portaCOM'] == '_':
				self.MsgA = "Escolha uma Porta!"
			else:
				self.MsgA = str(e)
			return 0
		return 0
	
	def openConfig(self):
		try:			
			print('Arquivo config nao existe.')
			with open('Resources/plugins/PythonScripts/PI_ArdThrottle_config.json', 'r') as json_file:
				self.configs = json.load(json_file)
		except IOError:
			with open('Resources/plugins/PythonScripts/PI_ArdThrottle_config.json', 'w') as json_file:
				json.dump(self.configs, json_file, indent = 4)
			print('Arquivo config criado com sucesso!')
		return 1

	def saveConfig(self):
		try:				
			with open('Resources/plugins/PythonScripts/PI_ArdThrottle_config.json', 'w') as json_file:
				json.dump(self.configs, json_file, indent = 4)
			self.MsgB = "     Ajuste Salvo!"
			print('Configs salvas com sucesso!')
			return 1
		except IOError:
			self.MsgB = 'Erro em salvar'
			print('Erro em salvar config, saveConfig()')
			return 0
		return 0

	def calibrarJoystick(self):
		if self.calibrar:
			if self.data[0] < self.configs['stepSpeedBMin']:
				self.configs['stepSpeedBMin'] = self.data[0]-1
			if self.data[0] > self.configs['stepSpeedBMax']:
				self.configs['stepSpeedBMax'] = self.data[0]+1
			if self.data[1] < self.configs['stepThrottleLMin']:
				self.configs['stepThrottleLMin'] = self.data[1]-1
			if self.data[1] > self.configs['stepThrottleLMax']:
				self.configs['stepThrottleLMax'] = self.data[1]+1
			if self.data[2] < self.configs['stepThrottleRMin']:
				self.configs['stepThrottleRMin'] = self.data[2]-1
			if self.data[2] > self.configs['stepThrottleRMax']:
				self.configs['stepThrottleRMax'] = self.data[2]+1
			if self.data[3] < self.configs['stepPropellerMin']:
				self.configs['stepPropellerMin'] = self.data[3]-1
			if self.data[3] > self.configs['stepPropellerMax']:
				self.configs['stepPropellerMax'] = self.data[3]+1
			if self.data[4] < self.configs['stepMixtureMin']:
				self.configs['stepMixtureMin'] = self.data[4]-1
			if self.data[4] > self.configs['stepMixtureMax']:
				self.configs['stepMixtureMax'] = self.data[4]+1
			if self.data[5] < self.configs['stepFlapMin']:
				self.configs['stepFlapMin'] = self.data[5]-1
			if self.data[5] > self.configs['stepFlapMax']:
				self.configs['stepFlapMax'] = self.data[5]+1
				
		XPSetWidgetDescriptor(self.joySpeedBrake, '1 - ['+str(self.configs['stepSpeedBMin'])+'/'+str(self.configs['stepSpeedBMax'])+'] - '+str(self.data[0]))
		XPSetWidgetDescriptor(self.joyThrottleL, '2 - ['+str(self.configs['stepThrottleLMin'])+'/'+str(self.configs['stepThrottleLMax'])+'] - '+str(self.data[1]))
		XPSetWidgetDescriptor(self.joyThrottleR, '3 - ['+str(self.configs['stepThrottleRMin'])+'/'+str(self.configs['stepThrottleRMax'])+'] - '+str(self.data[2]))
		XPSetWidgetDescriptor(self.joyPropeller, '4 - ['+str(self.configs['stepPropellerMin'])+'/'+str(self.configs['stepPropellerMax'])+'] - '+str(self.data[3]))
		XPSetWidgetDescriptor(self.joyMixture, '5 - ['+str(self.configs['stepMixtureMin'])+'/'+str(self.configs['stepMixtureMax'])+'] - '+str(self.data[4]))
		XPSetWidgetDescriptor(self.joyFlaps, '6 - ['+str(self.configs['stepFlapMin'])+'/'+str(self.configs['stepFlapMax'])+'] - '+str(self.data[5]))

		return

	def calibrarPropeller(self):
		prop = XPLMGetDataf(self.DataRefPropellerAll)
		if prop < self.configs['stepPropellerAdjustMin']:
			self.configs['stepPropellerAdjustMin'] = prop
		if prop > self.configs['stepPropellerAdjustMax']:
			self.configs['stepPropellerAdjustMax'] = prop

		XPSetWidgetDescriptor(self.textPropAdjust, "Min " + str(int(self.configs['stepPropellerAdjustMin'])) + ' | Max ' + str(int(self.configs['stepPropellerAdjustMax'])))

		return

	def WhiteLEDS(self):
		GEARDOWN1DEF = XPLMGetDataf(self.DataRefGear1def)
		GEARDOWN2DEF = XPLMGetDataf(self.DataRefGear2def)
		GEARDOWN3DEF = XPLMGetDataf(self.DataRefGear3def)
		PARKB = int(XPLMGetDataf(self.DataRefParkingBrake))

		self.LEDS = "LD"
		# --------------------------------------- Gear Down L
		if GEARDOWN1DEF == 1:
			self.LEDS += "01"
		elif GEARDOWN1DEF == 0:
			self.LEDS += "00"
		else:
			self.LEDS += "10"
		# --------------------------------------- Gear Down C
		if GEARDOWN2DEF == 1:
			self.LEDS += "01"
		elif GEARDOWN2DEF == 0:
			self.LEDS += "00"
		else:
			self.LEDS += "10"
		# --------------------------------------- Gear Down R
		if GEARDOWN3DEF == 1:
			self.LEDS += "01"
		elif GEARDOWN3DEF == 0:
			self.LEDS += "00"
		else:
			self.LEDS += "10"
		# --------------------------------------- Parking Brake
		if PARKB == 1:
			self.LEDS += "1"
		else:
			self.LEDS += "0"
		self.LEDS += ","

		return

	def configflaps(self):
		qtdFlaps = self.configs['qtdFlaps']
		if qtdFlaps < 2:
			qtdFlaps = 2
		fator = 1.0/(qtdFlaps-1)
		self.flapsPositions = []
		self.flapsMedia = [0.0]
		for i in range(qtdFlaps):
			self.flapsPositions.append((fator*i))
		for i in range(qtdFlaps-1):
			self.flapsMedia.append((self.flapsPositions[i]+self.flapsPositions[i+1])/2)		
		self.flapsMedia.append(1.0)
		self.saveConfig()
	
	def flapsAdjust(self, flaps):
		for i in range(self.configs['qtdFlaps']+1):
			if flaps >= self.flapsMedia[i] and flaps <= self.flapsMedia[i+1]:
				return self.flapsPositions[i]
		return 0

	def stepRange(self, value, limitMin, limitMax):
		if value <= limitMin:
			return limitMin
		if value >= limitMax:
			return limitMax
		return value

	def FloopCallback(self, elapsedMe, elapsedSim, counter, refcon):
		if self.connected:
			self.WhiteLEDS()

			writeAgain = False
			stepSpeedBFit = self.configs['stepSpeedBMax'] - self.configs['stepSpeedBMin']
			stepThrottleLFit = self.configs['stepThrottleLMax'] - self.configs['stepThrottleLMin']
			stepThrottleRFit = self.configs['stepThrottleRMax'] - self.configs['stepThrottleRMin']
			stepPropellerFit = self.configs['stepPropellerMax'] - self.configs['stepPropellerMin']
			stepMixtureFit = self.configs['stepMixtureMax'] - self.configs['stepMixtureMin']
			stepFlapFit = self.configs['stepFlapMax'] - self.configs['stepFlapMin']
			stepPropellerAdjustFit = self.configs['stepPropellerAdjustMax'] - self.configs['stepPropellerAdjustMin']

			if self.ardSerial.isOpen():

				if self.flagConfigWindow:
					self.timeCloseConfigWindow += 1
					if self.timeCloseConfigWindow >= 100:
						if self.configWindow:
							XPDestroyWidget(self, self.configWindowWidget, 1)
							self.configWindow = False
							self.timeCloseConfigWindow = 0
							self.flagConfigWindow = False

				if self.LEDS != self.LEDSLastState:
					self.ardSerial.write(self.LEDS)
					self.LEDSLastState = self.LEDS
					writeAgain = True

				while self.ardSerial.inWaiting() > 0:
					readData = []
					inSerial = self.ardSerial.readline()
					readData = inSerial.split(",")
					if readData[0] == "P":
						try:
							self.data[0] = int(readData[1])
							self.data[1] = int(readData[2])
							self.data[2] = int(readData[3])
							self.data[3] = int(readData[4])
							self.data[4] = int(readData[5])
							self.data[5] = int(readData[6])
						except:
							pass
						self.Potenciometros["A"] = self.stepRange(1-(1.0/stepSpeedBFit)*(self.data[0]-self.configs['stepSpeedBMin']), 0.0, 1.0)
						self.Potenciometros["B"] = self.stepRange((1.0/stepThrottleLFit)*(self.data[1]-self.configs['stepThrottleLMin']), 0.0, 1.0)
						self.Potenciometros["C"] = self.stepRange((1.0/stepThrottleRFit)*(self.data[2]-self.configs['stepThrottleRMin']), 0.0, 1.0)
						if self.ka350DRef:
							self.Potenciometros["D"] = self.stepRange((1.0/stepPropellerFit)*(self.data[3]-self.configs['stepPropellerMin']), 0.0, 1.0) #Propeller KA350	
						else:
							self.Potenciometros["D"] = self.stepRange(self.configs['stepPropellerAdjustMin'] + (stepPropellerAdjustFit/stepPropellerFit)*(self.data[3]-self.configs['stepPropellerMin']), self.configs['stepPropellerAdjustMin'], self.configs['stepPropellerAdjustMax']) #angulo do propeller
						self.Potenciometros["E"] = self.stepRange((1.0/stepMixtureFit)*(self.data[4]-self.configs['stepMixtureMin']), 0.0, 1.0)
						flaps = self.stepRange(1-(1.0/stepFlapFit)*(self.data[5]-self.configs['stepFlapMin']), 0.0, 1.0)
						
						self.Potenciometros["F"] = self.flapsAdjust(flaps)

						self.throttle[0] = self.Potenciometros["B"]
						self.throttle[1] = self.Potenciometros["C"]
						self.prop[0] = self.Potenciometros["D"]
						self.prop[1] = self.Potenciometros["D"]
						self.prop[2] = self.Potenciometros["D"]

					XPLMSetDataf(self.DataRefSpeedBrake, self.Potenciometros["A"])
					XPLMSetDataf(self.DataRefMixtureAll, self.Potenciometros["E"])
					XPLMSetDataf(self.DataRefFlap, self.Potenciometros["F"])

					if XPLMGetDatai(self.DataRefAutoTh) == 0:
						if self.tolissDRef:
							XPLMSetDatavf(self.TOLISSDataRefThrottle, self.throttle, 0, 2)
						else:
							XPLMSetDatavf(self.DataRefThrottle, self.throttle, 0, 2)

					if self.ka350DRef:
						XPLMSetDatavf(self.KA350DataRefProp, self.prop, 0, 3)
					else:
						XPLMSetDatavf(self.DataRefPropeller, self.prop, 0, 2)

					if self.ziboDRef:
						if self.Potenciometros["A"] > 0:
							XPLMSetDataf(self.ZIBODataRefSpeedBrakeStop, 1.0)
						else:
							XPLMSetDataf(self.ZIBODataRefSpeedBrakeStop, 0.0)
						XPLMSetDataf(self.ZIBODataRefSpeedBrake, self.Potenciometros["A"])
						XPLMSetDataf(self.ZIBODataRefFlap, self.Potenciometros["F"])

				if self.calibrarWindow:
					self.calibrarJoystick()
					if self.calibarProp:
						self.calibrarPropeller()

				if writeAgain == True:
					self.ardSerial.write(self.LEDS)
					writeAgain = False
					
		return 0.1
		
	def XPluginStop(self):
		pass

	def XPluginEnable(self):
		return 1

	def XPluginDisable(self):
		pass

	def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
		pass
