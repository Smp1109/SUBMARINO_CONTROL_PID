#!/usr/bin/env python3
import serial
import socket
import threading
import time
import json
import re

HOST = '0.0.0.0'
PORT = 5000
PUERTO_SERIAL = '/dev/ttyUSB0'
BAUDRATE = 115200

class BridgeUltraRapido:
    def __init__(self):
        self.serial_esp = None
        self.clientes = []
        self.ejecutando = True
        self.lock_clientes = threading.Lock()
        
        # Datos de sensores
        self.distancia = 0
        self.confianza = 0
        self.ax = 0.0
        self.ay = 0.0
        self.az = 0.0
        self.presion_mbar = 0.0
        self.profundidad_m = 0.0
        self.temperatura_c = 0.0
        self.presion_ok = False
        self.luz_estado = 0
        
        # Control de tiempo
        self.ultimo_envio_json = 0
        self.ultimo_envio_consulta = 0
        self.frame_count = 0
        self.last_fps_time = time.time()
        
        self.buffer = ""

    def conectar_serial(self):
        try:
            self.serial_esp = serial.Serial(
                port=PUERTO_SERIAL,
                baudrate=BAUDRATE,
                timeout=0.001
            )
            time.sleep(0.5)
            print(f"[BRIDGE] ✅ Conectado a ESP32 en {PUERTO_SERIAL}")
            
            # Activar modo stream
            time.sleep(0.1)
            self.serial_esp.write(b'{"tipo":"stream","estado":1}\n')
            self.serial_esp.flush()
            print("[BRIDGE] ✅ Stream activado")
            return True
        except Exception as e:
            print(f"[BRIDGE] ❌ Error: {e}")
            return False

    def parsear_datos(self, linea):
        try:
            if linea.startswith('{'):
                try:
                    datos = json.loads(linea)
                    if 'presion' in datos:
                        p = datos['presion']
                        self.presion_mbar = p.get('mbar', 0)
                        self.profundidad_m = p.get('profundidad_m', 0)
                        self.temperatura_c = p.get('temperatura_c', 0)
                        self.presion_ok = p.get('ok', False)
                    if 'sonar' in datos:
                        s = datos['sonar']
                        self.distancia = s.get('distancia_cm', 0)
                        self.confianza = s.get('confianza', 0)
                    if 'mpu' in datos:
                        m = datos['mpu']
                        self.ax = m.get('ax', 0)
                        self.ay = m.get('ay', 0)
                        self.az = m.get('az', 0)
                    if 'luz' in datos:
                        self.luz_estado = 1 if datos['luz'].get('encendida', False) else 0
                    
                    self.enviar_datos_a_clientes()
                    
                    self.frame_count += 1
                    ahora = time.time()
                    if ahora - self.last_fps_time >= 1.0:
                        print(f"[BRIDGE] ⚡ {self.frame_count} Hz | Clientes: {len(self.clientes)}")
                        self.frame_count = 0
                        self.last_fps_time = ahora
                    return True
                except:
                    pass
            return False
        except:
            return False

    def enviar_datos_a_clientes(self):
        if not self.clientes:
            return

        datos = {
            "distancia": self.distancia,
            "confianza": self.confianza,
            "ax": round(self.ax, 2),
            "ay": round(self.ay, 2),
            "az": round(self.az, 2),
            "luz": self.luz_estado,
            "presion": {
                "mbar": round(self.presion_mbar, 1),
                "profundidad_m": round(self.profundidad_m, 2),
                "temperatura_c": round(self.temperatura_c, 1),
                "ok": self.presion_ok
            },
            "timestamp": int(time.time() * 1000)
        }

        mensaje = json.dumps(datos) + '\n'
        mensaje_bytes = mensaje.encode()

        with self.lock_clientes:
            for cliente in self.clientes[:]:
                try:
                    cliente.send(mensaje_bytes)
                except:
                    self.clientes.remove(cliente)

    def leer_serial(self):
        while self.ejecutando:
            try:
                if self.serial_esp and self.serial_esp.in_waiting > 0:
                    datos = self.serial_esp.read(self.serial_esp.in_waiting)
                    texto = datos.decode('utf-8', errors='ignore')
                    self.buffer += texto
                    
                    while '\n' in self.buffer:
                        linea, self.buffer = self.buffer.split('\n', 1)
                        linea = linea.strip()
                        if not linea:
                            continue
                        
                        self.parsear_datos(linea)
                        
                        if 'luz_response' in linea or 'movimiento_response' in linea:
                            with self.lock_clientes:
                                for cliente in self.clientes[:]:
                                    try:
                                        cliente.send((linea + '\n').encode())
                                    except:
                                        self.clientes.remove(cliente)
                else:
                    time.sleep(0.0005)
            except Exception as e:
                print(f"[BRIDGE] Error: {e}")
                time.sleep(0.001)

    def enviar_comando_esp32(self, comando):
        if not self.serial_esp or not self.serial_esp.is_open:
            return None

        try:
            mensaje = json.dumps(comando) + '\n'
            self.serial_esp.write(mensaje.encode())
            self.serial_esp.flush()
            
            if comando.get('tipo') == 'movimiento':
                return '{"tipo":"movimiento_response","estado":"ok"}'
            
            tiempo_espera = time.time() + 0.2
            respuesta = ""
            while time.time() < tiempo_espera:
                if self.serial_esp.in_waiting > 0:
                    datos = self.serial_esp.read(self.serial_esp.in_waiting)
                    texto = datos.decode('utf-8', errors='ignore')
                    respuesta += texto
                    if 'response' in respuesta:
                        for line in respuesta.split('\n'):
                            if line.strip().startswith('{'):
                                return line.strip()
                time.sleep(0.005)
            return None
        except Exception as e:
            print(f"[BRIDGE] ❌ Error: {e}")
            return None

    def manejar_cliente(self, conn, addr):
        print(f"[BRIDGE] ✅ Cliente conectado desde {addr}")
        with self.lock_clientes:
            self.clientes.append(conn)

        try:
            conn.settimeout(0.1)
            while self.ejecutando:
                try:
                    data = conn.recv(4096)
                    if not data:
                        break

                    texto = data.decode('utf-8', errors='ignore').strip()
                    if not texto or len(texto) < 3:
                        continue

                    try:
                        comando = json.loads(texto)
                        tipo = comando.get('tipo')
                        
                        if tipo == 'movimiento':
                            respuesta = self.enviar_comando_esp32(comando)
                            if respuesta:
                                conn.send((respuesta + '\n').encode())
                        
                        elif tipo == 'luz':
                            respuesta = self.enviar_comando_esp32(comando)
                            if respuesta:
                                conn.send((respuesta + '\n').encode())
                            else:
                                conn.send(b'{"tipo":"error","mensaje":"No response"}\n')
                        
                        elif tipo == 'consultar_sensores':
                            respuesta = self.enviar_comando_esp32(comando)
                            if respuesta:
                                conn.send((respuesta + '\n').encode())
                            else:
                                datos_locales = {
                                    "tipo": "datos_sensores",
                                    "presion": {
                                        "mbar": round(self.presion_mbar, 1),
                                        "profundidad_m": round(self.profundidad_m, 2),
                                        "temperatura_c": round(self.temperatura_c, 1),
                                        "ok": self.presion_ok
                                    },
                                    "sonar": {
                                        "distancia_cm": self.distancia,
                                        "confianza": self.confianza
                                    },
                                    "mpu": {
                                        "ax": round(self.ax, 2),
                                        "ay": round(self.ay, 2),
                                        "az": round(self.az, 2)
                                    },
                                    "luz": {
                                        "encendida": self.luz_estado == 1
                                    }
                                }
                                conn.send((json.dumps(datos_locales) + '\n').encode())
                        else:
                            conn.send(b'{"tipo":"error","mensaje":"Comando no soportado"}\n')
                    except:
                        pass
                except socket.timeout:
                    continue
                except Exception as e:
                    break
        except:
            pass
        finally:
            with self.lock_clientes:
                if conn in self.clientes:
                    self.clientes.remove(conn)
            conn.close()
            print(f"[BRIDGE] Cliente {addr} desconectado")

    def iniciar(self):
        if not self.conectar_serial():
            print("[BRIDGE] ⚠️ No se pudo conectar")
            return

        threading.Thread(target=self.leer_serial, daemon=True).start()

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen(10)

        print(f"[BRIDGE] �� Servidor ULTRA RÁPIDO en {HOST}:{PORT}")
        print("[BRIDGE] Esperando clientes...")

        try:
            while self.ejecutando:
                server.settimeout(0.1)
                try:
                    conn, addr = server.accept()
                    threading.Thread(target=self.manejar_cliente, args=(conn, addr), daemon=True).start()
                except socket.timeout:
                    continue
        except KeyboardInterrupt:
            print("\n[BRIDGE] Cerrando...")
        finally:
            self.ejecutando = False
            server.close()
            if self.serial_esp:
                self.serial_esp.close()

if __name__ == "__main__":
    bridge = BridgeUltraRapido()
    bridge.iniciar()
