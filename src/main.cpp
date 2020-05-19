#include <Arduino.h>

// Declarações dos Potenciômetros
#define potenciometroA A0
#define potenciometroB A1
#define potenciometroC A2
#define potenciometroD A3
#define potenciometroE A4
#define potenciometroF A5
// Declarações dos LEDS
#define	Right_Gear_Green 2
#define	Nose_Gear_Green 3
#define	Left_Gear_Green 4
#define	Right_Gear_Red 5
#define	Nose_Gear_Red 6
#define	Left_Gear_Red 7
#define	Parking_Brake_Ann 8
// Declarações dos Botões
#define AT 22
#define Reverse 24

// variáveis usadas para salvar o estado anterior dos potenciômetros
int potALastState = 0;
int potBLastState = 0;
int potCLastState = 0;
int potDLastState = 0;
int potELastState = 0;
int potFLastState = 0;
// variável para minimizar o ruído dos potenciômetros
int Correction = 5;
// variáveis para salvar as strings q serão enviadas via serial para o simulador
String dataPotenciometers = "P,0000,0000,0000,0000,0000,0000,"; // a vírgula do final serve para o split do python separar o valor do \n
String stateLEDS = "0000000";
// flag usada para controlar o envio de dados via serial, apenas quando existem mudanças nos dados.
bool flagSend = false;

void setup() {
  pinMode(potenciometroA, INPUT);
  pinMode(potenciometroB, INPUT);
  pinMode(potenciometroC, INPUT);
  pinMode(potenciometroD, INPUT);
  pinMode(potenciometroE, INPUT);
  pinMode(potenciometroF, INPUT);
  pinMode(Right_Gear_Green, OUTPUT);
  pinMode(Nose_Gear_Green, OUTPUT);
  pinMode(Left_Gear_Green, OUTPUT);
  pinMode(Right_Gear_Red, OUTPUT);
  pinMode(Nose_Gear_Red, OUTPUT);
  pinMode(Left_Gear_Red, OUTPUT);
  pinMode(Parking_Brake_Ann, OUTPUT);
  Serial.begin(115200);
  delay(1000);
}

void updateLEDS(){  // método para atualizar os LEDS
  if (stateLEDS[0] == '1'){
    digitalWrite(Nose_Gear_Red,1);
  }else{
    digitalWrite(Nose_Gear_Red,0);
  }
  if (stateLEDS[1] == '1'){
    digitalWrite(Nose_Gear_Green,1);
  }else{
    digitalWrite(Nose_Gear_Green,0);
  }
  if (stateLEDS[2] == '1'){
    digitalWrite(Right_Gear_Red,1);
  }else{
    digitalWrite(Right_Gear_Red,0);
  }
  if (stateLEDS[3] == '1'){
    digitalWrite(Right_Gear_Green,1);
  }else{
    digitalWrite(Right_Gear_Green,0);
  }
  if (stateLEDS[4] == '1'){
    digitalWrite(Left_Gear_Red,1);
  }else{
    digitalWrite(Left_Gear_Red,0);
  }
  if (stateLEDS[5] == '1'){
    digitalWrite(Left_Gear_Green,1);
  }else{
    digitalWrite(Left_Gear_Green,0);
  }
  if (stateLEDS[6] == '1'){
    digitalWrite(Parking_Brake_Ann,1);
  }else{
    digitalWrite(Parking_Brake_Ann,0);
  }
}

void serial(){  // método que verifica se existem dados para ler na porta serial
  if (Serial.available()) {
    char inChar = Serial.read();
    if (inChar == 'D'){
      for (int i=0; i<8; i++){
        char inSerial = Serial.read();
        if (inSerial == ','){
          updateLEDS();
          break;
        }
        stateLEDS[i] = inSerial;
      }
    }
  }
}

String INCZERO(int number){ // método para colocar zeros a esquerda
  String zeroFront = "";
  if (number < 1000){
    zeroFront += "0";
  }
  if (number < 100){
    zeroFront += "0";
  }
  if (number < 10){
    zeroFront += "0";
  }
  if (number <= 0){
    zeroFront += "0";
  }else{
    zeroFront += String(number);
  }
  return zeroFront;
}

void updatePot(int value, int position){  // método para atualizar os dados dos potenciômetros
  String valueString = "";
  valueString = INCZERO(value);
  int fimArray = (5*position)+1;
  int j = 0;
  for (int i=fimArray-4; i<fimArray; i++){
    dataPotenciometers[i] = valueString[j];
    j++;
  }  
  flagSend = true;  // ativar a flag para poder enviar os dados via serial
}

void loop() {
  // lendo os dados dos potenciômetros constantemente
  int potA = analogRead(potenciometroA);
  int potB = analogRead(potenciometroB);
  int potC = analogRead(potenciometroC);
  int potD = analogRead(potenciometroD);
  int potE = analogRead(potenciometroE);
  int potF = analogRead(potenciometroF);

  // se os dados dos potenciômetros + a correção mudarem, fazer a atualização da lista com os dados para transmitir
  if ((potA > (potALastState+Correction)) || (potA < (potALastState-Correction))){updatePot(potA, 1); potALastState = potA;}
  if ((potB > (potBLastState+Correction)) || (potB < (potBLastState-Correction))){updatePot(potB, 2); potBLastState = potB;}
  if ((potC > (potCLastState+Correction)) || (potC < (potCLastState-Correction))){updatePot(potC, 3); potCLastState = potC;}
  if ((potD > (potDLastState+Correction)) || (potD < (potDLastState-Correction))){updatePot(potD, 4); potDLastState = potD;}
  if ((potE > (potELastState+Correction)) || (potE < (potELastState-Correction))){updatePot(potE, 5); potELastState = potE;}
  if ((potF > (potFLastState+Correction)) || (potF < (potFLastState-Correction))){updatePot(potF, 6); potFLastState = potF;}
  
  // flag utilizada para enviar os dados via serial, apenas quando tem alteração
  if (flagSend){
    Serial.println(dataPotenciometers);
    flagSend = false; // fechando a flag para não ficar enviando dados sempre q o loop repete, e sem mudança nos dados
  }

  // chamando o método que analisa a entrada serial, a fim de receber dados do simulador
  serial();
}