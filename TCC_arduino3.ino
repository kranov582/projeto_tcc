#include <DallasTemperature.h>
#include <OneWire.h>
#include <Wire.h>
#include <ClosedCube_HDC1080.h>
#include <HX711.h>
#include <EEPROM.h>

#define pSENSOR         7
#define pCONTROLE       3
#define DT A1
#define SCK A0
#define ld 2

char c;
float t;
float p;
float i;
float d;

OneWire ourWire(pSENSOR); //CONFIGURA UMA INSTÂNCIA ONEWIRE PARA SE COMUNICAR COM O SENSOR
DallasTemperature sensors(&ourWire); //BIBLIOTECA DallasTemperature UTILIZA A OneWire
ClosedCube_HDC1080 hdc1080;
HX711 escala;

class TemperatureController{
public:
  
  double error;
  double temp;
  double lastemp;
  double kP, kI, kD;      
  double P, I, D;
  double pid;
  bool parar;
  
  double setPoint;
  long lastProcess;

  void  begin();
  void  run();
  float getHumidity();
  float getKP();
    return kP;
  float getKI();
    return kI;
  float getKD();
    return kD;
  void  setPID(float KP, float KI, float KD);
    kP = KP
    kI = KI
    kD = KD
  void  setSetPoint(float setpoint);
  void  start();
  void  stop();
  
  PID(double _kP, double _kI, double _kD){
    kP = _kP;
    kI = _kI;
    kD = _kD;
  }
  
  void addNewSample(double _temp){
    temp = _temp;
  }
  
  void setSetPoint(double _setPoint){
    setPoint = _setPoint;
  }
  
  double process(){
    // Implementação PID
    error = setPoint - temp;
    float deltaTime = (millis() - lastProcess) / 1000.0;
    lastProcess = millis();
    
    //P
    P = error * kP;
    
    //I
    I = I + (error * kI) * deltaTime;
    
    //D
    D = (lastemp - temp) * kD / deltaTime;
    lastemp = temp;
    
    // Soma tudo
    pid = P + I + D;
    if (parar == false){
      return pid;
    }
    if (parar == true){
      return 0;
    }
  }
};

PID meuPid(0,0,0);

void setup() {
  Serial.begin(9600); //Inicia o serial
  hdc1080.begin(0x40); //Inicia o sensor de umidade
  sensors.begin(); //INICIA O SENSOR de temp
  pinMode(pSENSOR, INPUT);
  pinMode(pCONTROLE, OUTPUT);
  pinMode(ld, OUTPUT);

  //celula de carga
  escala.begin (DT, SCK);
  escala.set_scale(1783.937875);
  escala.tare(20);

  meuPid.setSetPoint(60);
  meuPid.parar = true;
}

int controlePwm = 0;

void loop() {
  //Lê temp e umidade do sensor de umidade
  float t = hdc1080.readTemperature();
  float h = hdc1080.readHumidity();
  
  // Lê temperatura
  sensors.setWaitForConversion(false);
  sensors.requestTemperatures();//SOLICITA QUE A FUNÇÃO INFORME A TEMPERATURA DO SENSOR
  double temperature = sensors.getTempCByIndex(0);
  sensors.setWaitForConversion(true);
  double peso = escala.get_units(20);
  auto tempoatual = millis()/1000;
  
  // Manda pro objeto PID!
  meuPid.addNewSample(temperature);
  

  
  // Converte para controle
    controlePwm = (meuPid.process());
    if (controlePwm >= 255){
      controlePwm = 255;
    }
    if (controlePwm <= 0){
      controlePwm = 0;
    }
    if (controlePwm == 0){
      digitalWrite(ld, LOW);
    }
    if (controlePwm > 0){
      digitalWrite(ld, HIGH);
    }
 
  //Teclas
  if (Serial.available() > 0) { // Verificar se há caracteres disponíveis
      c = Serial.read();
    if (c == 's'){
      meuPid.parar = true;
      digitalWrite(ld, LOW);
     }
    if (c == 'r'){
      meuPid.parar = false;
      meuPid.I = 0;
      digitalWrite(ld, HIGH);
     }
    if (c == 't'){
      t = Serial.parseFloat();
       meuPid.setSetPoint(t);
     }
    if (c == 'p'){
      p = Serial.parseFloat();
       meuPid.kP = p;
      }
    if (c == 'i'){
      i = Serial.parseFloat();
       meuPid.kI = i;
      }
     if (c == 'd'){
      d = Serial.parseFloat();
       meuPid.kD = d;
      }
    }
   // Saída do controle
  analogWrite(pCONTROLE, controlePwm);
  Serial.print(controlePwm);
  Serial.print(" ,");
  Serial.print(temperature);
  Serial.print(" ,");
  Serial.print(peso);
  Serial.print(" ,");
  Serial.print(h);
  Serial.print(" ,");
  Serial.print(meuPid.setPoint);
  Serial.print(",");
  Serial.print(meuPid.kP);
  Serial.print(",");
  Serial.print(meuPid.kI);
  Serial.print(",");
  Serial.print(meuPid.kD);
  Serial.print(",");
  Serial.print(tempoatual);
  Serial.println(",");
  delay(1000);
}
