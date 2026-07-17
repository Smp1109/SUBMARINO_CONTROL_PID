import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from tkinter import filedialog
import socket
import json
import threading
import math
import os
import time
import re
import cv2
import numpy as np
from PIL import Image, ImageTk
import struct
import queue
import sys
import multiprocessing

# Intentar importar pygame
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("[MANDO] ⚠️ Pygame no disponible")

try:
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False


# ============================================
# CLIENTE DE VIDEO
# ============================================
class VideoClient:
    def __init__(self, host='192.168.2.2', port=8555):
        self.host = host
        self.port = port
        self.sock = None
        self.connected = False
        self.frame = None
        self.running = True
        self.buffer = b''
        self.frame_size = 0

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.host, self.port))
            self.connected = True
            print(f"[VIDEO] ✅ Conectado al servidor en {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"[VIDEO] ❌ Error conectando: {e}")
            return False

    def receive_frame(self):
        if not self.connected:
            return None

        try:
            if len(self.buffer) < 4:
                data = self.sock.recv(4 - len(self.buffer))
                if not data:
                    return None
                self.buffer += data

            if len(self.buffer) >= 4 and self.frame_size == 0:
                self.frame_size = struct.unpack('>I', self.buffer[:4])[0]
                self.buffer = self.buffer[4:]

            if self.frame_size > 0:
                while len(self.buffer) < self.frame_size:
                    data = self.sock.recv(self.frame_size - len(self.buffer))
                    if not data:
                        return None
                    self.buffer += data

                frame_data = self.buffer[:self.frame_size]
                self.buffer = self.buffer[self.frame_size:]
                self.frame_size = 0

                nparr = np.frombuffer(frame_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is not None:
                    self.frame = img
                    return img

            return self.frame

        except socket.timeout:
            return self.frame
        except Exception as e:
            print(f"[VIDEO] Error recibiendo frame: {e}")
            self.connected = False
            return None

    def close(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass


# ============================================
# VENTANA DE CONFIGURACIÓN DE PWM
# ============================================
class PWMConfigWindow:
    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent.root)
        self.window.title("⚙️ CONFIGURACIÓN DE PWM")
        self.window.geometry("400x350")
        self.window.configure(bg="#0a0a1a")
        self.window.resizable(False, False)
        
        self.window.protocol("WM_DELETE_WINDOW", self.cerrar)
        
        # Variables
        self.pwm_velocidad_var = tk.StringVar(value=f"{parent.PWM_VELOCIDAD}")
        self.pwm_neutro_var = tk.StringVar(value=f"{parent.PWM_NEUTRO}")
        
        self.setup_ui()
        
    def setup_ui(self):
        # Título
        titulo = tk.Label(self.window, text="⚙️ CONFIGURACIÓN DE PWM", 
                         font=("Arial", 16, "bold"), bg="#0a0a1a", fg="#00b4d8")
        titulo.pack(pady=(15, 5))
        
        tk.Label(self.window, text="Ajusta los valores de PWM para control manual", 
                font=("Arial", 10), bg="#0a0a1a", fg="#888888").pack(pady=(0, 15))
        
        # Frame principal
        frame = tk.Frame(self.window, bg="#0d1117", highlightbackground="#1f2429", highlightthickness=2)
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        # ==========================================
        # 1. PWM VELOCIDAD (Emerger / Sumergir)
        # ==========================================
        tk.Label(frame, text="⬆⬇ VELOCIDAD (Emerger / Sumergir)", 
                font=("Arial", 11, "bold"), bg="#0d1117", fg="#00b4d8").pack(pady=(15, 0))
        
        velocidad_frame = tk.Frame(frame, bg="#0d1117")
        velocidad_frame.pack(pady=(5, 5))
        
        tk.Label(velocidad_frame, text="Valor (µs):", font=("Arial", 10), 
                bg="#0d1117", fg="#888888").pack(side=tk.LEFT, padx=(0, 5))
        
        self.velocidad_entry = tk.Entry(velocidad_frame, textvariable=self.pwm_velocidad_var,
                                       font=("Arial", 14), width=10, justify='center',
                                       bg="#1a1a2e", fg="#00b4d8", insertbackground="#00b4d8",
                                       relief=tk.FLAT, highlightbackground="#1f2429", highlightthickness=1)
        self.velocidad_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        self.velocidad_btn = tk.Button(velocidad_frame, text="Aplicar", 
                                      command=self.aplicar_velocidad,
                                      bg="#1f2429", fg="#00b4d8", font=("Arial", 9, "bold"),
                                      relief=tk.RAISED, bd=2)
        self.velocidad_btn.pack(side=tk.LEFT)
        
        # Mostrar valores calculados
        self.info_velocidad = tk.Label(frame, 
                                 text=f"⬆ Emerger: {self.parent.PWM_EMERGER} µs | ⬇ Sumergir: {self.parent.PWM_SUMERGER} µs",
                                 font=("Arial", 9, "bold"), bg="#0d1117", fg="#ffaa44")
        self.info_velocidad.pack(pady=(5, 0))
        
        tk.Label(frame, text=f"Rango: 10 - {self.parent.PWM_NEUTRO - 1100} µs", 
                font=("Arial", 8), bg="#0d1117", fg="#666666").pack()
        
        tk.Label(frame, text="⬆ L2 = Emerger | ⬇ R2 = Sumergir (misma velocidad)", 
                font=("Arial", 8), bg="#0d1117", fg="#888888").pack(pady=(0, 5))
        
        # Separador
        tk.Frame(frame, height=1, bg="#1f2429").pack(fill=tk.X, pady=10, padx=20)
        
        # ==========================================
        # 2. PWM NEUTRO (Punto de equilibrio)
        # ==========================================
        tk.Label(frame, text="🎯 NEUTRO REAL (Punto de equilibrio)", 
                font=("Arial", 11, "bold"), bg="#0d1117", fg="#ffaa44").pack(pady=(0, 0))
        
        neutro_frame = tk.Frame(frame, bg="#0d1117")
        neutro_frame.pack(pady=(5, 10))
        
        tk.Label(neutro_frame, text="Valor (µs):", font=("Arial", 10), 
                bg="#0d1117", fg="#888888").pack(side=tk.LEFT, padx=(0, 5))
        
        self.neutro_entry = tk.Entry(neutro_frame, textvariable=self.pwm_neutro_var,
                                    font=("Arial", 14), width=10, justify='center',
                                    bg="#1a1a2e", fg="#ffaa44", insertbackground="#ffaa44",
                                    relief=tk.FLAT, highlightbackground="#1f2429", highlightthickness=1)
        self.neutro_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        self.neutro_btn = tk.Button(neutro_frame, text="Aplicar", 
                                   command=self.aplicar_neutro,
                                   bg="#1f2429", fg="#ffaa44", font=("Arial", 9, "bold"),
                                   relief=tk.RAISED, bd=2)
        self.neutro_btn.pack(side=tk.LEFT)
        
        tk.Label(frame, text="El ROV se mantiene en esta posición (sin subir ni bajar)", 
                font=("Arial", 8), bg="#0d1117", fg="#666666").pack()
        
        # ==========================================
        # INFORMACIÓN ADICIONAL (PWM Detenido fijo)
        # ==========================================
        tk.Frame(frame, height=1, bg="#1f2429").pack(fill=tk.X, pady=10, padx=20)
        
        info_detenido = tk.Label(frame, 
                                text="⏹ Botón Círculo = DETENER MOTORES (1500 µs) [FIJO]", 
                                font=("Arial", 8, "bold"), bg="#0d1117", fg="#888888")
        info_detenido.pack(pady=(0, 10))
        
        # ==========================================
        # INFORMACIÓN ACTUAL
        # ==========================================
        info_frame = tk.Frame(self.window, bg="#0a0a1a")
        info_frame.pack(fill=tk.X, padx=15, pady=10)
        
        tk.Label(info_frame, text="📊 VALORES ACTUALES", 
                font=("Arial", 9, "bold"), bg="#0a0a1a", fg="#00b4d8").pack()
        
        self.info_label = tk.Label(info_frame, 
                                  text=f"⚡ Velocidad: {self.parent.PWM_VELOCIDAD}µs | 🎯 Neutro: {self.parent.PWM_NEUTRO}µs",
                                  font=("Arial", 9), bg="#0a0a1a", fg="#e0e0e0")
        self.info_label.pack(pady=5)
        
        # ==========================================
        # BOTONES
        # ==========================================
        btn_frame = tk.Frame(self.window, bg="#0a0a1a")
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="💾 Guardar", 
                 command=self.guardar_configuracion,
                 bg="#1f2429", fg="#00ff88", font=("Arial", 10, "bold"),
                 relief=tk.RAISED, bd=2, padx=20, pady=8).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="📂 Cargar", 
                 command=self.cargar_configuracion,
                 bg="#1f2429", fg="#ffaa44", font=("Arial", 10, "bold"),
                 relief=tk.RAISED, bd=2, padx=20, pady=8).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="↺ Restaurar", 
                 command=self.restaurar_default,
                 bg="#1f2429", fg="#ff6b6b", font=("Arial", 9, "bold"),
                 relief=tk.RAISED, bd=2, padx=15, pady=8).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="❌ Cerrar", 
                 command=self.cerrar,
                 bg="#444444", fg="white", font=("Arial", 10, "bold"),
                 relief=tk.RAISED, bd=2, padx=20, pady=8).pack(side=tk.LEFT, padx=5)
        
        # Actualizar información inicial
        self.actualizar_info_velocidad()
    
    def actualizar_info_velocidad(self):
        """Actualiza la información de emerger/sumergir"""
        neutro = self.parent.PWM_NEUTRO
        velocidad = self.parent.PWM_VELOCIDAD
        self.info_velocidad.config(
            text=f"⬆ Emerger: {neutro - velocidad} µs | ⬇ Sumergir: {neutro + velocidad} µs"
        )
    
    def actualizar_pid_con_nuevo_neutro(self):
        """Actualiza los parámetros del PID basados en el nuevo neutro"""
        try:
            nuevo_neutro = self.parent.PWM_NEUTRO
            neutro_original = 1574
            factor_escala = nuevo_neutro / neutro_original
            
            kp_actual = self.parent.kp
            ki_actual = self.parent.ki
            kd_actual = self.parent.kd
            
            self.parent.kp = round(max(0.1, min(10.0, kp_actual * factor_escala)), 6)
            self.parent.ki = round(max(0.0, min(5.0, ki_actual * factor_escala)), 6)
            self.parent.kd = round(max(0.0, min(3.0, kd_actual * factor_escala)), 6)
            
            if self.parent.pid_window is not None:
                try:
                    if self.parent.pid_window.winfo_exists():
                        self.parent.pid_window.kp_var.set(f"{self.parent.kp:.6f}")
                        self.parent.pid_window.ki_var.set(f"{self.parent.ki:.6f}")
                        self.parent.pid_window.kd_var.set(f"{self.parent.kd:.6f}")
                        self.parent.pid_window.actualizar_pid_label()
                except:
                    pass
            
            self.parent.integral = 0
            self.parent.error_anterior = 0
            self.parent.pid_salida = 0
            
            print(f"[PID] 🔄 Parámetros ajustados para nuevo neutro {nuevo_neutro}µs:")
            print(f"   Kp: {kp_actual:.6f} → {self.parent.kp:.6f}")
            print(f"   Ki: {ki_actual:.6f} → {self.parent.ki:.6f}")
            print(f"   Kd: {kd_actual:.6f} → {self.parent.kd:.6f}")
            
        except Exception as e:
            print(f"[PID] ❌ Error actualizando PID: {e}")
    
    def aplicar_velocidad(self):
        """Aplica la velocidad de emerger/sumergir"""
        try:
            valor = int(self.pwm_velocidad_var.get())
            neutro = self.parent.PWM_NEUTRO
            
            if 10 <= valor <= (neutro - 1100):
                self.parent.PWM_VELOCIDAD = valor
                self.parent.PWM_EMERGER = neutro - valor
                self.parent.PWM_SUMERGER = neutro + valor
                
                self.velocidad_entry.config(fg="#00b4d8")
                self.actualizar_info_velocidad()
                self.actualizar_info()
                self.parent.actualizar_labels_pwm()
                
                print(f"[PWM] ⚡ Velocidad: {valor}µs (Emerger: {neutro-valor}µs | Sumergir: {neutro+valor}µs)")
                messagebox.showinfo("Éxito", 
                                   f"✅ Velocidad actualizada a {valor}µs\n\n"
                                   f"⬆ Emerger: {neutro - valor}µs\n"
                                   f"⬇ Sumergir: {neutro + valor}µs")
            else:
                self.pwm_velocidad_var.set(f"{self.parent.PWM_VELOCIDAD}")
                messagebox.showerror("Error", 
                                   f"El valor debe estar entre 10 y {neutro - 1100}µs")
        except ValueError:
            messagebox.showerror("Error", "Ingrese un número válido")
            self.pwm_velocidad_var.set(f"{self.parent.PWM_VELOCIDAD}")
    
    def aplicar_neutro(self):
        """Aplica el neutro real y actualiza el PID"""
        try:
            valor = int(self.pwm_neutro_var.get())
            velocidad = self.parent.PWM_VELOCIDAD
            
            if (1100 + velocidad) <= valor <= (1900 - velocidad):
                neutro_anterior = self.parent.PWM_NEUTRO
                
                self.parent.PWM_NEUTRO = valor
                self.parent.pwm_vertical = valor
                self.parent.PWM_EMERGER = valor - velocidad
                self.parent.PWM_SUMERGER = valor + velocidad
                
                self.actualizar_pid_con_nuevo_neutro()
                
                self.neutro_entry.config(fg="#ffaa44")
                self.actualizar_info_velocidad()
                self.actualizar_info()
                self.parent.actualizar_labels_pwm()
                
                print(f"[PWM] 🎯 Neutro cambiado: {neutro_anterior}µs → {valor}µs")
                messagebox.showinfo("Éxito", 
                                   f"✅ Neutro actualizado a {valor}µs\n\n"
                                   f"⬆ Emerger: {self.parent.PWM_EMERGER}µs\n"
                                   f"⬇ Sumergir: {self.parent.PWM_SUMERGER}µs\n\n"
                                   f"🔄 Parámetros PID ajustados automáticamente:\n"
                                   f"Kp={self.parent.kp:.6f} | Ki={self.parent.ki:.6f} | Kd={self.parent.kd:.6f}")
            else:
                self.pwm_neutro_var.set(f"{self.parent.PWM_NEUTRO}")
                messagebox.showerror("Error", 
                                   f"El neutro debe estar entre {1100 + velocidad} y {1900 - velocidad}µs")
        except ValueError:
            messagebox.showerror("Error", "Ingrese un número válido")
            self.pwm_neutro_var.set(f"{self.parent.PWM_NEUTRO}")
    
    def actualizar_info(self):
        """Actualiza la información mostrada"""
        self.info_label.config(
            text=f"⚡ Velocidad: {self.parent.PWM_VELOCIDAD}µs | 🎯 Neutro: {self.parent.PWM_NEUTRO}µs"
        )
    
    def guardar_configuracion(self):
        """Guarda la configuración en un archivo"""
        try:
            with open("pwm_config.txt", "w") as f:
                f.write("# CONFIGURACIÓN DE PWM PARA EL ROV\n")
                f.write("# ================================\n\n")
                f.write(f"PWM_VELOCIDAD = {self.parent.PWM_VELOCIDAD}\n")
                f.write(f"PWM_NEUTRO = {self.parent.PWM_NEUTRO}\n\n")
                f.write("# VALORES DERIVADOS:\n")
                f.write(f"PWM_EMERGER = {self.parent.PWM_EMERGER}\n")
                f.write(f"PWM_SUMERGER = {self.parent.PWM_SUMERGER}\n\n")
                f.write("# VALORES RECOMENDADOS:\n")
                f.write("# PWM_VELOCIDAD = 174  (Distancia desde el neutro)\n")
                f.write("# PWM_NEUTRO = 1574    (Punto de equilibrio)\n")
                f.write("# RESULTADO:\n")
                f.write("# ⬆ Emerger: 1400µs | ⬇ Sumergir: 1600µs\n")
                f.write("# ⏹ Botón Círculo = 1500µs (FIJO - Motores detenidos)\n")
            
            messagebox.showinfo("Éxito", f"✅ Configuración guardada en:\npwm_config.txt")
            print("[PWM] Configuración guardada")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar: {e}")
    
    def cargar_configuracion(self):
        """Carga la configuración desde un archivo"""
        try:
            with open("pwm_config.txt", "r") as f:
                lineas = f.readlines()
                
            for linea in lineas:
                linea = linea.strip()
                if linea.startswith("#") or not linea:
                    continue
                if "=" in linea:
                    clave, valor = linea.split("=")
                    clave = clave.strip()
                    valor = int(valor.strip())
                    
                    if clave == "PWM_VELOCIDAD":
                        if 10 <= valor <= (self.parent.PWM_NEUTRO - 1100):
                            self.parent.PWM_VELOCIDAD = valor
                            self.pwm_velocidad_var.set(str(valor))
                    elif clave == "PWM_NEUTRO":
                        if 1100 <= valor <= 1900:
                            self.parent.PWM_NEUTRO = valor
                            self.parent.pwm_vertical = valor
                            self.pwm_neutro_var.set(str(valor))
            
            neutro = self.parent.PWM_NEUTRO
            velocidad = self.parent.PWM_VELOCIDAD
            self.parent.PWM_EMERGER = neutro - velocidad
            self.parent.PWM_SUMERGER = neutro + velocidad
            
            self.actualizar_info_velocidad()
            self.actualizar_info()
            self.parent.actualizar_labels_pwm()
            self.actualizar_pid_con_nuevo_neutro()
            
            messagebox.showinfo("Éxito", "✅ Configuración cargada correctamente")
            print("[PWM] Configuración cargada")
            
        except FileNotFoundError:
            messagebox.showwarning("No encontrado", "No hay archivo de configuración guardado")
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar: {e}")
    
    def restaurar_default(self):
        """Restaura los valores por defecto"""
        respuesta = messagebox.askyesno("Restaurar", 
                                       "¿Restaurar valores por defecto?\n\n"
                                       "⚡ Velocidad: 174µs\n"
                                       "🎯 Neutro: 1574µs\n\n"
                                       "Resultado:\n"
                                       "⬆ Emerger: 1400µs\n"
                                       "⬇ Sumergir: 1600µs\n"
                                       "⏹ Botón Círculo: 1500µs (FIJO)")
        
        if respuesta:
            self.parent.PWM_VELOCIDAD = 174
            self.parent.PWM_NEUTRO = 1574
            self.parent.PWM_EMERGER = 1400
            self.parent.PWM_SUMERGER = 1600
            self.parent.pwm_vertical = 1574
            self.parent.kp = -0.324684094115606
            self.parent.ki = -0.0163490058089125
            self.parent.kd = -1.17117582298324
            self.parent.integral = 0
            self.parent.error_anterior = 0
            self.parent.pid_salida = 0
            
            if self.parent.pid_window is not None:
                try:
                    if self.parent.pid_window.winfo_exists():
                        self.parent.pid_window.kp_var.set("-0.324684094115606")
                        self.parent.pid_window.ki_var.set("-0.0163490058089125")
                        self.parent.pid_window.kd_var.set("-1.17117582298324")
                        self.parent.pid_window.actualizar_pid_label()
                except:
                    pass
            
            self.pwm_velocidad_var.set("174")
            self.pwm_neutro_var.set("1574")
            
            self.actualizar_info_velocidad()
            self.actualizar_info()
            self.parent.actualizar_labels_pwm()
            
            messagebox.showinfo("Éxito", "✅ Valores por defecto restaurados")
            print("[PWM] Valores por defecto restaurados")
    
    def cerrar(self):
        self.parent.pwm_config_window = None
        self.window.destroy()


# ============================================
# VENTANA DE AJUSTE PI
# ============================================
class PIWindow:
    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent.root)
        self.window.title("AJUSTE PI - Compensación de Inclinación")
        self.window.geometry("420x450")
        self.window.configure(bg="#0a0a1a")
        self.window.resizable(False, False)

        self.window.protocol("WM_DELETE_WINDOW", self.cerrar)

        self.kp_var = tk.StringVar(value=f"{parent.compensacion_kp:.2f}")
        self.ki_var = tk.StringVar(value=f"{parent.compensacion_ki:.2f}")

        self.setup_ui()
        self.actualizar_datos_tiempo_real()

    def setup_ui(self):
        titulo = tk.Label(self.window, text="AJUSTE PI - COMPENSACIÓN EN LAPTOP",
                         font=("Arial", 14, "bold"), bg="#0a0a1a", fg="#00b4d8")
        titulo.pack(pady=(15, 5))

        tk.Label(self.window, text="El cálculo de compensación se hace en la laptop",
                font=("Arial", 9), bg="#0a0a1a", fg="#888888").pack(pady=(0, 15))

        frame_params = tk.Frame(self.window, bg="#0d1117", highlightbackground="#1f2429", highlightthickness=2)
        frame_params.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        tk.Label(frame_params, text="Kp (Proporcional)",
                font=("Arial", 10, "bold"), bg="#0d1117", fg="#00b4d8").pack(pady=(15, 0))

        kp_frame = tk.Frame(frame_params, bg="#0d1117")
        kp_frame.pack(pady=(5, 10))

        self.kp_label = tk.Label(kp_frame, text="Valor:", font=("Arial", 10), bg="#0d1117", fg="#888888")
        self.kp_label.pack(side=tk.LEFT, padx=(0, 5))

        self.kp_entry = tk.Entry(kp_frame, textvariable=self.kp_var,
                                font=("Arial", 14), width=8, justify='center',
                                bg="#1a1a2e", fg="#00ff88", insertbackground="#00ff88",
                                relief=tk.FLAT, highlightbackground="#1f2429", highlightthickness=1)
        self.kp_entry.pack(side=tk.LEFT, padx=(0, 10))

        self.kp_apply_btn = tk.Button(kp_frame, text="Aplicar", command=self.aplicar_kp,
                                     bg="#1f2429", fg="#00ff88", font=("Arial", 9, "bold"), relief=tk.RAISED, bd=2)
        self.kp_apply_btn.pack(side=tk.LEFT)

        tk.Label(frame_params, text="Responde a la inclinación (0-10)", font=("Arial", 8), bg="#0d1117", fg="#666666").pack()

        tk.Label(frame_params, text="Ki (Integral)",
                font=("Arial", 10, "bold"), bg="#0d1117", fg="#00b4d8").pack(pady=(15, 0))

        ki_frame = tk.Frame(frame_params, bg="#0d1117")
        ki_frame.pack(pady=(5, 10))

        self.ki_label = tk.Label(ki_frame, text="Valor:", font=("Arial", 10), bg="#0d1117", fg="#888888")
        self.ki_label.pack(side=tk.LEFT, padx=(0, 5))

        self.ki_entry = tk.Entry(ki_frame, textvariable=self.ki_var,
                                font=("Arial", 14), width=8, justify='center',
                                bg="#1a1a2e", fg="#ffaa44", insertbackground="#ffaa44",
                                relief=tk.FLAT, highlightbackground="#1f2429", highlightthickness=1)
        self.ki_entry.pack(side=tk.LEFT, padx=(0, 10))

        self.ki_apply_btn = tk.Button(ki_frame, text="Aplicar", command=self.aplicar_ki,
                                     bg="#1f2429", fg="#ffaa44", font=("Arial", 9, "bold"), relief=tk.RAISED, bd=2)
        self.ki_apply_btn.pack(side=tk.LEFT)

        tk.Label(frame_params, text="Elimina el error de inclinación (0-10)", font=("Arial", 8), bg="#0d1117", fg="#666666").pack()

        frame_info = tk.Frame(self.window, bg="#0a0a1a")
        frame_info.pack(fill=tk.X, padx=15, pady=10)

        tk.Label(frame_info, text="INFORMACIÓN EN TIEMPO REAL",
                font=("Arial", 9, "bold"), bg="#0a0a1a", fg="#00b4d8").pack()

        self.info_frame = tk.Frame(frame_info, bg="#0d1117", highlightbackground="#1f2429", highlightthickness=1)
        self.info_frame.pack(fill=tk.X, pady=5)

        self.lbl_angulo = tk.Label(self.info_frame, text="Ángulo: 0.0°",
                                   font=("Arial", 10), bg="#0d1117", fg="#00ff88")
        self.lbl_angulo.pack(side=tk.LEFT, padx=10, pady=5)

        self.lbl_compensacion = tk.Label(self.info_frame, text="Comp: 0 µs",
                                        font=("Arial", 10), bg="#0d1117", fg="#ffaa44")
        self.lbl_compensacion.pack(side=tk.RIGHT, padx=10, pady=5)

        self.lbl_estado = tk.Label(frame_info, text="Estado: ✅ COMPENSACIÓN ACTIVA",
                                   font=("Arial", 9), bg="#0a0a1a", fg="#00ff88")
        self.lbl_estado.pack(pady=2)

        self.lbl_pi_actual = tk.Label(frame_info,
                                      text=f"PI: Kp={self.parent.compensacion_kp:.2f} Ki={self.parent.compensacion_ki:.2f}",
                                      font=("Arial", 8), bg="#0a0a1a", fg="#00b4d8")
        self.lbl_pi_actual.pack(pady=2)

        btn_frame = tk.Frame(self.window, bg="#0a0a1a")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="DESACTIVAR", command=self.toggle_compensacion,
                 bg="#444444", fg="white", font=("Arial", 9, "bold"),
                 relief=tk.RAISED, bd=2, padx=15, pady=5).pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text="ACTIVAR", command=self.activar_compensacion,
                 bg="#00ff88", fg="black", font=("Arial", 9, "bold"),
                 relief=tk.RAISED, bd=2, padx=15, pady=5).pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text="Valores Recomendados", command=self.valores_recomendados,
                 bg="#1f2429", fg="white", font=("Arial", 9, "bold"),
                 relief=tk.RAISED, bd=2, padx=15, pady=5).pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text="Cerrar", command=self.cerrar,
                 bg="#444444", fg="white", font=("Arial", 9, "bold"),
                 relief=tk.RAISED, bd=2, padx=15, pady=5).pack(side=tk.LEFT, padx=5)

    def toggle_compensacion(self):
        self.parent.compensacion_activa = False
        self.parent.compensacion_integral = 0
        self.lbl_estado.config(text="Estado: ❌ COMPENSACIÓN INACTIVA", fg="#ff6b6b")
        print("[COMPENSACIÓN] ❌ DESACTIVADA")
        self.parent.agregar_evento(("actualizar_estado_compensacion", False))

    def activar_compensacion(self):
        self.parent.compensacion_activa = True
        self.lbl_estado.config(text="Estado: ✅ COMPENSACIÓN ACTIVA", fg="#00ff88")
        print("[COMPENSACIÓN] ✅ ACTIVADA")
        self.parent.agregar_evento(("actualizar_estado_compensacion", True))

    def aplicar_kp(self):
        try:
            valor = float(self.kp_var.get())
            if -10 <= valor <= 10:
                self.parent.compensacion_kp = valor
                self.kp_var.set(f"{valor:.2f}")
                self.actualizar_pi_label()
                print(f"[PI] Kp actualizado a: {valor:.2f}")
            else:
                self.kp_var.set(f"{self.parent.compensacion_kp:.2f}")
                messagebox.showerror("Error", "Kp debe estar entre 0 y 10")
        except ValueError:
            self.kp_var.set(f"{self.parent.compensacion_kp:.2f}")
            messagebox.showerror("Error", "Ingrese un valor numérico válido")

    def aplicar_ki(self):
        try:
            valor = float(self.ki_var.get())
            if 10 <= valor <= 10:
                self.parent.compensacion_ki = valor
                self.ki_var.set(f"{valor:.2f}")
                self.actualizar_pi_label()
                print(f"[PI] Ki actualizado a: {valor:.2f}")
            else:
                self.ki_var.set(f"{self.parent.compensacion_ki:.2f}")
                messagebox.showerror("Error", "Ki debe estar entre 0 y 10")
        except ValueError:
            self.ki_var.set(f"{self.parent.compensacion_ki:.2f}")
            messagebox.showerror("Error", "Ingrese un valor numérico válido")

    def actualizar_pi_label(self):
        if hasattr(self, 'lbl_pi_actual'):
            self.lbl_pi_actual.config(text=f"PI: Kp={self.parent.compensacion_kp:.2f} Ki={self.parent.compensacion_ki:.2f}")

    def valores_recomendados(self):
        self.parent.compensacion_kp = 1.5
        self.parent.compensacion_ki = 1.0
        self.kp_var.set("1.50")
        self.ki_var.set("1.00")
        self.actualizar_pi_label()
        print("[PI] Valores recomendados aplicados: Kp=1.5, Ki=1.0")
        messagebox.showinfo("Éxito", "Valores recomendados aplicados:\nKp=1.5, Ki=1.0")

    def actualizar_datos_tiempo_real(self):
        if hasattr(self.parent, 'compensacion_angulo'):
            self.lbl_angulo.config(text=f"Ángulo: {self.parent.compensacion_angulo:.1f}°")
            if abs(self.parent.compensacion_angulo) < 2:
                self.lbl_angulo.config(fg="#00ff88")
            elif abs(self.parent.compensacion_angulo) < 5:
                self.lbl_angulo.config(fg="#ffaa44")
            else:
                self.lbl_angulo.config(fg="#ff6b6b")
        
        if hasattr(self.parent, 'compensacion_salida'):
            self.lbl_compensacion.config(text=f"Comp: {self.parent.compensacion_salida:.0f} µs")
        
        self.window.after(200, self.actualizar_datos_tiempo_real)

    def cerrar(self):
        self.parent.pi_window = None
        self.window.destroy()


# ============================================
# VENTANA DE AJUSTE PID (MODIFICADA PARA 6 DECIMALES)
# ============================================
class PIDWindow:
    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent.root)
        self.window.title("AJUSTE PID - Control de Altura")
        self.window.geometry("380x500")
        self.window.configure(bg="#0a0a1a")
        self.window.resizable(False, False)

        self.window.protocol("WM_DELETE_WINDOW", self.cerrar)

        # MODIFICADO: Usar 6 decimales
        self.kp_var = tk.StringVar(value=f"{parent.kp:.6f}")
        self.ki_var = tk.StringVar(value=f"{parent.ki:.6f}")
        self.kd_var = tk.StringVar(value=f"{parent.kd:.6f}")

        self.setup_ui()
        self.actualizar_datos()

    def setup_ui(self):
        titulo = tk.Label(self.window, text="AJUSTE PID - Control de Altura",
                         font=("Arial", 16, "bold"), bg="#0a0a1a", fg="#00b4d8")
        titulo.pack(pady=(15, 5))

        tk.Label(self.window, text="Ajuste de parámetros para control de altura con Sonar",
                font=("Arial", 9), bg="#0a0a1a", fg="#888888").pack(pady=(0, 15))

        frame_params = tk.Frame(self.window, bg="#0d1117", highlightbackground="#1f2429", highlightthickness=2)
        frame_params.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        tk.Label(frame_params, text="Kp (Proporcional)",
                font=("Arial", 10, "bold"), bg="#0d1117", fg="#00b4d8").pack(pady=(15, 0))

        kp_frame = tk.Frame(frame_params, bg="#0d1117")
        kp_frame.pack(pady=(5, 10))

        self.kp_label = tk.Label(kp_frame, text="Valor:", font=("Arial", 10), bg="#0d1117", fg="#888888")
        self.kp_label.pack(side=tk.LEFT, padx=(0, 5))

        self.kp_entry = tk.Entry(kp_frame, textvariable=self.kp_var,
                                font=("Arial", 14), width=12, justify='center',
                                bg="#1a1a2e", fg="#00ff88", insertbackground="#00ff88",
                                relief=tk.FLAT, highlightbackground="#1f2429", highlightthickness=1)
        self.kp_entry.pack(side=tk.LEFT, padx=(0, 10))

        self.kp_apply_btn = tk.Button(kp_frame, text="Aplicar", command=self.aplicar_kp,
                                     bg="#1f2429", fg="#00ff88", font=("Arial", 9, "bold"), relief=tk.RAISED, bd=2)
        self.kp_apply_btn.pack(side=tk.LEFT)

        tk.Label(frame_params, text="Responde al error de altura (-20 a 20)", font=("Arial", 8), bg="#0d1117", fg="#666666").pack()

        tk.Label(frame_params, text="Ki (Integral)",
                font=("Arial", 10, "bold"), bg="#0d1117", fg="#00b4d8").pack(pady=(15, 0))

        ki_frame = tk.Frame(frame_params, bg="#0d1117")
        ki_frame.pack(pady=(5, 10))

        self.ki_label = tk.Label(ki_frame, text="Valor:", font=("Arial", 10), bg="#0d1117", fg="#888888")
        self.ki_label.pack(side=tk.LEFT, padx=(0, 5))

        self.ki_entry = tk.Entry(ki_frame, textvariable=self.ki_var,
                                font=("Arial", 14), width=12, justify='center',
                                bg="#1a1a2e", fg="#ffaa44", insertbackground="#ffaa44",
                                relief=tk.FLAT, highlightbackground="#1f2429", highlightthickness=1)
        self.ki_entry.pack(side=tk.LEFT, padx=(0, 10))

        self.ki_apply_btn = tk.Button(ki_frame, text="Aplicar", command=self.aplicar_ki,
                                     bg="#1f2429", fg="#ffaa44", font=("Arial", 9, "bold"), relief=tk.RAISED, bd=2)
        self.ki_apply_btn.pack(side=tk.LEFT)

        tk.Label(frame_params, text="Elimina el error estacionario de altura (-10 a 10)", font=("Arial", 8), bg="#0d1117", fg="#666666").pack()

        tk.Label(frame_params, text="Kd (Derivativo)",
                font=("Arial", 10, "bold"), bg="#0d1117", fg="#00b4d8").pack(pady=(15, 0))

        kd_frame = tk.Frame(frame_params, bg="#0d1117")
        kd_frame.pack(pady=(5, 10))

        self.kd_label = tk.Label(kd_frame, text="Valor:", font=("Arial", 10), bg="#0d1117", fg="#888888")
        self.kd_label.pack(side=tk.LEFT, padx=(0, 5))

        self.kd_entry = tk.Entry(kd_frame, textvariable=self.kd_var,
                                font=("Arial", 14), width=12, justify='center',
                                bg="#1a1a2e", fg="#ff6b6b", insertbackground="#ff6b6b",
                                relief=tk.FLAT, highlightbackground="#1f2429", highlightthickness=1)
        self.kd_entry.pack(side=tk.LEFT, padx=(0, 10))

        self.kd_apply_btn = tk.Button(kd_frame, text="Aplicar", command=self.aplicar_kd,
                                     bg="#1f2429", fg="#ff6b6b", font=("Arial", 9, "bold"), relief=tk.RAISED, bd=2)
        self.kd_apply_btn.pack(side=tk.LEFT)

        tk.Label(frame_params, text="Reduce oscilaciones en altura (-5 a 5)", font=("Arial", 8), bg="#0d1117", fg="#666666").pack()

        frame_info = tk.Frame(self.window, bg="#0a0a1a")
        frame_info.pack(fill=tk.X, padx=15, pady=10)

        tk.Label(frame_info, text="INFORMACIÓN EN TIEMPO REAL",
                font=("Arial", 9, "bold"), bg="#0a0a1a", fg="#00b4d8").pack()

        self.info_frame = tk.Frame(frame_info, bg="#0d1117", highlightbackground="#1f2429", highlightthickness=1)
        self.info_frame.pack(fill=tk.X, pady=5)

        self.lbl_error = tk.Label(self.info_frame, text="Error: 0.00 m",
                                 font=("Arial", 10), bg="#0d1117", fg="#00ff88")
        self.lbl_error.pack(side=tk.LEFT, padx=10, pady=5)

        self.lbl_salida = tk.Label(self.info_frame, text="Salida: 0%",
                                  font=("Arial", 10), bg="#0d1117", fg="#ffaa44")
        self.lbl_salida.pack(side=tk.RIGHT, padx=10, pady=5)

        self.lbl_altura = tk.Label(frame_info, text="Altura actual: 0.00 m | Deseada: 0.00 m",
                                   font=("Arial", 9), bg="#0a0a1a", fg="#888888")
        self.lbl_altura.pack(pady=2)

        self.lbl_pid_actual = tk.Label(frame_info,
                                      text=f"PID: Kp={self.parent.kp:.6f} Ki={self.parent.ki:.6f} Kd={self.parent.kd:.6f}",
                                      font=("Arial", 8), bg="#0a0a1a", fg="#00b4d8")
        self.lbl_pid_actual.pack(pady=2)

        btn_frame = tk.Frame(self.window, bg="#0a0a1a")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Valores Recomendados", command=self.valores_recomendados,
                 bg="#1f2429", fg="white", font=("Arial", 9, "bold"),
                 relief=tk.RAISED, bd=2, padx=15, pady=5).pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text="Cerrar", command=self.cerrar,
                 bg="#444444", fg="white", font=("Arial", 9, "bold"),
                 relief=tk.RAISED, bd=2, padx=15, pady=5).pack(side=tk.LEFT, padx=5)

    def aplicar_kp(self):
        try:
            valor = float(self.kp_var.get())
            if -20 <= valor <= 20:
                self.parent.kp = valor
                self.kp_var.set(f"{valor:.6f}")  # MODIFICADO
                self.actualizar_pid_label()
                print(f"[PID] Kp actualizado a: {valor:.6f}")
            else:
                self.kp_var.set(f"{self.parent.kp:.6f}")  # MODIFICADO
                messagebox.showerror("Error", "Kp debe estar entre -20 y 20")
        except ValueError:
            self.kp_var.set(f"{self.parent.kp:.6f}")  # MODIFICADO
            messagebox.showerror("Error", "Ingrese un valor numérico válido")

    def aplicar_ki(self):
        try:
            valor = float(self.ki_var.get())
            if -10 <= valor <= 10:
                self.parent.ki = valor
                self.ki_var.set(f"{valor:.6f}")  # MODIFICADO
                self.actualizar_pid_label()
                print(f"[PID] Ki actualizado a: {valor:.6f}")
            else:
                self.ki_var.set(f"{self.parent.ki:.6f}")  # MODIFICADO
                messagebox.showerror("Error", "Ki debe estar entre -10 y 10")
        except ValueError:
            self.ki_var.set(f"{self.parent.ki:.6f}")  # MODIFICADO
            messagebox.showerror("Error", "Ingrese un valor numérico válido")

    def aplicar_kd(self):
        try:
            valor = float(self.kd_var.get())
            if -5 <= valor <= 5:
                self.parent.kd = valor
                self.kd_var.set(f"{valor:.6f}")  # MODIFICADO
                self.actualizar_pid_label()
                print(f"[PID] Kd actualizado a: {valor:.6f}")
            else:
                self.kd_var.set(f"{self.parent.kd:.6f}")  # MODIFICADO
                messagebox.showerror("Error", "Kd debe estar entre -5 y 5")
        except ValueError:
            self.kd_var.set(f"{self.parent.kd:.6f}")  # MODIFICADO
            messagebox.showerror("Error", "Ingrese un valor numérico válido")

    def actualizar_pid_label(self):
        if hasattr(self, 'lbl_pid_actual'):
            self.lbl_pid_actual.config(text=f"PID: Kp={self.parent.kp:.6f} Ki={self.parent.ki:.6f} Kd={self.parent.kd:.6f}")  # MODIFICADO

    def valores_recomendados(self):
        # MODIFICADO: Usar los valores de la imagen
        self.parent.kp = -0.324684094115606
        self.parent.ki = -0.0163490058089125
        self.parent.kd = -1.17117582298324
        self.kp_var.set("-0.324684094115606")
        self.ki_var.set("-0.0163490058089125")
        self.kd_var.set("-1.17117582298324")
        self.actualizar_pid_label()
        print("[PID] Valores aplicados")
        messagebox.showinfo("Éxito", "Valores aplicados correctamente")

    def actualizar_datos(self):
        if hasattr(self.parent, 'distancia_cm'):
            altura_actual = self.parent.distancia_cm / 100.0
            altura_deseada = self.parent.altura_deseada
            error = altura_deseada - altura_actual
            salida = self.parent.pid_salida * 100 if hasattr(self.parent, 'pid_salida') else 0

            self.lbl_error.config(text=f"Error: {error:+.2f} m")
            self.lbl_salida.config(text=f"Salida: {salida:+.1f}%")
            self.lbl_altura.config(text=f"Altura actual: {altura_actual:.2f} m | Deseada: {altura_deseada:.2f} m")

            if abs(error) < 0.05:
                self.lbl_error.config(fg="#00ff88")
            elif abs(error) < 0.2:
                self.lbl_error.config(fg="#ffaa44")
            else:
                self.lbl_error.config(fg="#ff6b6b")

        self.window.after(200, self.actualizar_datos)

    def cerrar(self):
        self.parent.pid_window = None
        self.window.destroy()


# ============================================
# INTERFAZ PRINCIPAL ROV
# ============================================
class ROVInterface:
    def __init__(self, root):
        self.root = root
        self.root.title("VEHÍCULO SUBMARINO - ROV Control")
        self.root.geometry("1020x770")
        self.root.configure(bg="#0a0a1a")

        # ==========================================
        # VARIABLES DE CONTROL
        # ==========================================
        self.running = True
        self.tiempo_inicio = time.time()
        
        self.bg_main = "#0a0a1a"
        self.panel_color = "#0d1117"
        self.border_color = "#1f2429"
        self.accent_color = "#00b4d8"
        self.warning_color = "#ff6b6b"
        self.success_color = "#00ff88"
        self.text_color = "#e0e0e0"
        
        self.distancia_cm = 0
        self.confianza = 0
        self.ax = 0.0
        self.ay = 0.0
        self.az = 0.0
        self.presion_mbar = 1013.25
        self.profundidad_m = 0.0
        self.temperatura_c = 25.0
        self.sensor_presion_ok = False
        self.compensacion_angulo = 0.0
        self.luz_encendida = False
        
        self.altura_deseada = 1.2
        self.modo_auto = False
        self.potencia = 50
        
        # ==========================================
        # CONSTANTES DE PWM - CONFIGURABLES
        # ==========================================
        self.PWM_VELOCIDAD = 174
        self.PWM_NEUTRO = 1572
        self.PWM_DETENIDO = 1500
        self.PWM_MIN = 1100
        self.PWM_MAX = 1900
        
        # Límites de saturación del PID
        self.PWM_PID_MIN = 1450
        self.PWM_PID_MAX = 1650
        
        # Valores derivados
        self.PWM_EMERGER = self.PWM_NEUTRO - self.PWM_VELOCIDAD
        self.PWM_SUMERGER = self.PWM_NEUTRO + self.PWM_VELOCIDAD
        
        self.pwm_vertical = self.PWM_NEUTRO
        
        # ==========================================
        # CONFIGURACIÓN PARA PING SONAR (BlueRobotics)
        # ==========================================
        self.escala_sonar = 20.0      # Escala de la gráfica (20 metros)
        self.profundidad_maxima = 50.0  # Profundidad máxima mostrada
        
        # Límites del sensor Ping Sonar
        self.DISTANCIA_MINIMA = 30      # 30cm (zona muerta oficial)
        self.DISTANCIA_MAXIMA = 10000   # 10000cm = 100 metros
        self.DISTANCIA_MINIMA_AUTO = 0.30  # 0.30 metros para modo automático
        
        # ==========================================
        # PARÁMETROS PID - VALORES DE LA IMAGEN
        # ==========================================
        self.kp = -0.324684094115606
        self.ki = -0.0163490058089125
        self.kd = -1.17117582298324
        self.error_anterior = 0
        self.integral = 0
        self.pid_salida = 0
        self.ultimo_tiempo_pid = time.time()
        
        # ==========================================
        # PARÁMETROS PI PARA COMPENSACIÓN
        # ==========================================
        self.compensacion_activa = True
        self.compensacion_kp = 1.5
        self.compensacion_ki = 1.0
        self.compensacion_integral = 0
        self.compensacion_salida = 0
        
        # ==========================================
        # FILTROS PARA EL SONAR
        # ==========================================
        self.distancia_anterior = 0
        self.lecturas_recientes = []
        self.MAX_LECTURAS_MEDIANA = 3  # Menos filtro necesario para Ping Sonar
        self.CONTADOR_LECTURAS_INVALIDAS = 0
        self.MAX_INVALIDAS = 5  # Más tolerante
        
        self.avance = 0.0
        self.giro = 0.0
        self.lateral = 0.0
        self.vertical = 0.0
        self.mando_conectado = False
        self.joystick = None
        self.ultimo_toggle_luz = 0
        
        self.historial = [0] * 80
        self.historial_error = [0] * 80
        self.historial_salida = [0] * 80
        self.historial_pwm = [self.PWM_NEUTRO] * 80
        self.historial_deseada = [self.altura_deseada] * 80
        self.historial_altura = [0] * 80
        self.historial_pwm_derecho = [self.PWM_NEUTRO] * 80
        self.historial_pwm_izquierdo = [self.PWM_NEUTRO] * 80
        
        self.sock = None
        self.socket_conectado = False
        self.bridge_ip = "192.168.2.2"
        self.bridge_port = 5000
        self.mensaje_reconectando = False
        
        self.video_client = None
        self.camera_connected = False
        self.camera_running = False
        self.frame = None
        
        self.pid_window = None
        self.pi_window = None
        self.pwm_config_window = None
        
        self.logo_img = None
        self.logo_label = None
        
        self.cola_eventos = queue.Queue()
        
        self.estado_detenido = False
        
        # ==========================================
        # PARA EL ANALIZADOR DE DATOS
        # ==========================================
        self.proceso_analizador = None
        self.analyzer_sock = None
        self.analyzer_conectado = False
        
        self.setup_ui()
        self.setup_joystick()
        
        threading.Thread(target=self.hilo_conexion, daemon=True).start()
        threading.Thread(target=self.hilo_mando, daemon=True).start()
        threading.Thread(target=self.hilo_pid, daemon=True).start()
        
        self.conectar_camara()
        
        self.procesar_cola_eventos()
        self.actualizar_interfaz()
    
    # ==========================================
    # FILTRO PARA EL SONAR (Optimizado para Ping Sonar)
    # ==========================================
    def filtrar_sonar(self, nueva_distancia_cm):
        """Filtro optimizado para Ping Sonar de BlueRobotics"""
        
        # 1. ZONA MUERTA (0.3m - especificación oficial)
        if nueva_distancia_cm < self.DISTANCIA_MINIMA:
            self.CONTADOR_LECTURAS_INVALIDAS += 1
            print(f"[SONAR] ⚠️ Zona muerta: {nueva_distancia_cm}cm")
            
            if self.CONTADOR_LECTURAS_INVALIDAS > self.MAX_INVALIDAS:
                self.CONTADOR_LECTURAS_INVALIDAS = 0
                if self.modo_auto:
                    print(f"[SONAR] ⚠️ Usando 100cm por seguridad")
                    return 100
                return self.distancia_cm if self.distancia_cm > 0 else 100
            
            if self.modo_auto and self.distancia_cm > 0:
                if self.distancia_cm > self.DISTANCIA_MINIMA:
                    return self.distancia_cm
            
            return self.distancia_cm if self.distancia_cm > 0 else 100
        
        # Resetear contador si hay lectura válida
        self.CONTADOR_LECTURAS_INVALIDAS = 0
        
        # 2. FILTRO DE RANGO MÁXIMO (100m)
        if nueva_distancia_cm > self.DISTANCIA_MAXIMA:
            print(f"[SONAR] ⚠️ Lectura fuera de rango: {nueva_distancia_cm}cm")
            return self.distancia_cm if self.distancia_cm > 0 else 500
        
        # 3. FILTRO DE MEDIANA (suave - el Ping ya es muy confiable)
        self.lecturas_recientes.append(nueva_distancia_cm)
        if len(self.lecturas_recientes) > self.MAX_LECTURAS_MEDIANA:
            self.lecturas_recientes.pop(0)
        
        if len(self.lecturas_recientes) >= 3:
            sorted_lecturas = sorted(self.lecturas_recientes)
            mediana = sorted_lecturas[len(sorted_lecturas) // 2]
            
            # Umbral más permisivo para el Ping Sonar
            if abs(nueva_distancia_cm - mediana) > 100:  # 1 metro de diferencia
                print(f"[SONAR] ⚠️ Pico detectado: {nueva_distancia_cm}cm - Usando mediana: {mediana}cm")
                return mediana
        
        # 4. FILTRO DE CAMBIO BRUSCO (más permisivo)
        if self.distancia_cm > 0:
            cambio = abs(nueva_distancia_cm - self.distancia_cm)
            if cambio > 200:  # 2 metros - el Ping puede medir cambios rápidos
                print(f"[SONAR] ⚠️ Cambio brusco: {cambio}cm - Limitando")
                if nueva_distancia_cm > self.distancia_cm:
                    return self.distancia_cm + 200
                else:
                    return max(self.DISTANCIA_MINIMA, self.distancia_cm - 200)
        
        return nueva_distancia_cm
    
    # ==========================================
    # MÉTODOS PARA EL ANALIZADOR DE DATOS
    # ==========================================
    
    def abrir_analizador(self):
        """Abre la ventana de análisis en un proceso separado"""
        try:
            if hasattr(self, 'proceso_analizador') and self.proceso_analizador is not None:
                if self.proceso_analizador.is_alive():
                    print("[ANALYZER] Ya está ejecutándose")
                    return
            
            try:
                from data_analyzer import ejecutar_analizador
            except ImportError:
                messagebox.showerror("Error", 
                    "No se encontró el archivo data_analyzer.py\n"
                    "Asegúrate de que esté en la misma carpeta")
                return
            
            self.proceso_analizador = multiprocessing.Process(
                target=ejecutar_analizador,
                name="DataAnalyzer",
                daemon=True
            )
            self.proceso_analizador.start()
            print("[ANALYZER] ✅ Proceso iniciado")
            
            threading.Thread(target=self.hilo_enviar_datos_analyzer, daemon=True).start()
            
        except Exception as e:
            print(f"[ANALYZER] ❌ Error: {e}")
            messagebox.showerror("Error", f"Error al abrir el analizador:\n{str(e)}")
    
    def hilo_enviar_datos_analyzer(self):
        """Hilo para enviar datos al programa de análisis"""
        intentos_conexion = 0
        while self.running:
            try:
                if not self.analyzer_conectado:
                    try:
                        if self.analyzer_sock:
                            try:
                                self.analyzer_sock.close()
                            except:
                                pass
                        
                        self.analyzer_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        self.analyzer_sock.settimeout(2.0)
                        self.analyzer_sock.connect(('127.0.0.1', 9999))
                        self.analyzer_conectado = True
                        intentos_conexion = 0
                        print("[ANALYZER] ✅ Conectado al servidor de análisis")
                    except socket.error as e:
                        intentos_conexion += 1
                        if intentos_conexion % 10 == 0:
                            print(f"[ANALYZER] ⚠️ Esperando conexión... (intento {intentos_conexion})")
                        time.sleep(1)
                        continue
                
                if self.distancia_cm > 0:
                    altura_actual = self.distancia_cm / 100.0
                    
                    pwm_base = self.pwm_vertical
                    if self.compensacion_activa and abs(self.compensacion_angulo) > 1.0:
                        compensacion = self.compensacion_kp * self.compensacion_angulo
                        compensacion = max(-300, min(300, compensacion))
                        pwm_derecho = pwm_base - int(compensacion)
                        pwm_izquierdo = pwm_base + int(compensacion)
                    else:
                        pwm_derecho = pwm_base
                        pwm_izquierdo = pwm_base
                    
                    dato = {
                        'tiempo': time.time() - self.tiempo_inicio,
                        'deseada': self.altura_deseada,
                        'medida': altura_actual,
                        'error': self.altura_deseada - altura_actual,
                        'salida_pid': self.pid_salida,
                        'pwm': self.pwm_vertical,
                        'pwm_derecho': pwm_derecho,
                        'pwm_izquierdo': pwm_izquierdo,
                        'angulo': self.compensacion_angulo,
                        'modo_auto': self.modo_auto,
                        'pwm_neutro': self.PWM_NEUTRO,
                        'altura_deseada': self.altura_deseada
                    }
                    
                    mensaje = json.dumps(dato) + '\n'
                    try:
                        self.analyzer_sock.send(mensaje.encode('utf-8'))
                    except (socket.error, BrokenPipeError):
                        self.analyzer_conectado = False
                        print("[ANALYZER] ❌ Error enviando, reconectando...")
                        time.sleep(1)
                        continue
                
                time.sleep(0.1)
                
            except socket.timeout:
                self.analyzer_conectado = False
                print("[ANALYZER] ⚠️ Timeout, reconectando...")
                time.sleep(1)
            except Exception as e:
                self.analyzer_conectado = False
                print(f"[ANALYZER] ❌ Error: {e}")
                time.sleep(1)
    
    def actualizar_labels_pwm(self):
        """Actualiza los labels de PWM cuando cambia la configuración"""
        try:
            if hasattr(self, 'lbl_emerger'):
                self.lbl_emerger.config(text=f"⬆ EMERGER: {self.PWM_EMERGER} µs")
            if hasattr(self, 'lbl_neutro'):
                self.lbl_neutro.config(text=f"🎯 NEUTRO: {self.PWM_NEUTRO} µs")
            if hasattr(self, 'lbl_sumergir'):
                self.lbl_sumergir.config(text=f"⬇ SUMERGIR: {self.PWM_SUMERGER} µs")
            
            if self.pwm_vertical == self.PWM_NEUTRO:
                self.pwm_vertical_label.config(text=f"{self.pwm_vertical} µs", fg="#ffaa44")
                
        except Exception as e:
            print(f"[PWM] Error actualizando labels: {e}")
    
    def abrir_pwm_config(self):
        """Abre la ventana de configuración de PWM"""
        try:
            if self.pwm_config_window is None:
                self.pwm_config_window = PWMConfigWindow(self)
            elif not self.pwm_config_window.winfo_exists():
                self.pwm_config_window = PWMConfigWindow(self)
            else:
                self.pwm_config_window.lift()
                self.pwm_config_window.focus_force()
        except Exception as e:
            print(f"[PWM] Error abriendo ventana: {e}")
            self.pwm_config_window = PWMConfigWindow(self)

    def setup_ui(self):
        main_frame = tk.Frame(self.root, bg=self.bg_main)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        top_frame = tk.Frame(main_frame, bg=self.bg_main)
        top_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        left_panel = tk.Frame(top_frame, bg=self.panel_color, highlightbackground=self.border_color, highlightthickness=1)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8), ipadx=8, ipady=8)

        logo_frame = tk.Frame(left_panel, bg=self.panel_color)
        logo_frame.pack(pady=(5, 3))

        try:
            ruta_logo = r"C:\Users\PREDATOR\Desktop\tesis\submarino\upse_logo.png"
            
            posibles_rutas = [
                ruta_logo,
                os.path.join(os.path.dirname(__file__), "upse_logo.png"),
                os.path.join(os.getcwd(), "upse_logo.png"),
                "upse_logo.png",
                "logo_upse.png",
                "/home/emanuel07/submarino/upse_logo.png"
            ]
            
            logo_cargado = False
            for ruta in posibles_rutas:
                if os.path.exists(ruta):
                    print(f"[LOGO] Intentando cargar desde: {ruta}")
                    img = Image.open(ruta)
                    img = img.resize((70, 70), Image.Resampling.LANCZOS)
                    self.logo_img = ImageTk.PhotoImage(img)
                    self.logo_label = tk.Label(logo_frame, image=self.logo_img, bg=self.panel_color)
                    self.logo_label.pack()
                    logo_cargado = True
                    print(f"[LOGO] ✅ Logo cargado desde: {ruta}")
                    break
            
            if not logo_cargado:
                tk.Label(logo_frame, text="🏛️", font=("Arial", 40), bg=self.panel_color, fg=self.accent_color).pack()
                tk.Label(logo_frame, text="UNIVERSIDAD ESTATAL\nPENÍNSULA DE SANTA ELENA",
                        font=("Arial", 8), bg=self.panel_color, fg=self.accent_color, justify='center').pack()
                print("[LOGO] ⚠️ No se encontró el archivo upse_logo.png, usando texto")
                
        except Exception as e:
            print(f"[LOGO] ❌ Error cargando logo: {e}")
            tk.Label(logo_frame, text="🏛️", font=("Arial", 40), bg=self.panel_color, fg=self.accent_color).pack()
            tk.Label(logo_frame, text="UNIVERSIDAD ESTATAL\nPENÍNSULA DE SANTA ELENA",
                    font=("Arial", 8), bg=self.panel_color, fg=self.accent_color, justify='center').pack()

        tk.Frame(left_panel, height=1, bg=self.border_color).pack(fill=tk.X, pady=3)

        tk.Label(left_panel, text="ALTURA DESEADA", font=("Arial", 11, "bold"), bg=self.panel_color, fg=self.accent_color).pack(pady=(5, 2))
        self.altura_deseada_label = tk.Label(left_panel, text=f"{self.altura_deseada:.1f} m", 
                                            font=("Arial", 30, "bold"), bg=self.panel_color, fg="white")
        self.altura_deseada_label.pack(pady=(0, 5))

        manual_frame = tk.Frame(left_panel, bg=self.panel_color)
        manual_frame.pack(pady=(0, 8))
        self.depth_entry = tk.Entry(manual_frame, width=8, font=("Arial", 12), justify='center')
        self.depth_entry.pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(manual_frame, text="SET", command=self.set_manual_height, 
                 bg=self.accent_color, fg="white", font=("Arial", 10, "bold"), width=5).pack(side=tk.LEFT)

        tk.Frame(left_panel, height=1, bg=self.border_color).pack(fill=tk.X, pady=5)

        auto_frame = tk.Frame(left_panel, bg=self.panel_color)
        auto_frame.pack(fill=tk.X, pady=(0, 3))

        tk.Label(auto_frame, text="MODO AUTO", font=("Arial", 11, "bold"), 
                bg=self.panel_color, fg=self.text_color).pack(side=tk.LEFT, padx=(0, 5))

        self.auto_led = tk.Canvas(auto_frame, width=18, height=18, bg=self.panel_color, highlightthickness=0)
        self.auto_led.pack(side=tk.LEFT, padx=(0, 5))
        self.auto_led.create_oval(2, 2, 16, 16, fill="#444444", outline="")

        self.auto_btn = tk.Button(auto_frame, text="DESACTIVADO", command=self.toggle_modo_auto,
                                 bg="#444444", fg="white", font=("Arial", 9, "bold"), width=12)
        self.auto_btn.pack(side=tk.LEFT)

        btn_pid_frame = tk.Frame(left_panel, bg=self.panel_color)
        btn_pid_frame.pack(fill=tk.X, pady=(0, 3))
        tk.Button(btn_pid_frame, text="⚙️ AJUSTE PID", command=self.abrir_ventana_pid,
                 bg="#1f2429", fg="#00b4d8", font=("Arial", 10, "bold"),
                 relief=tk.RAISED, bd=1, padx=5, pady=3, width=16).pack()

        btn_analizar_frame = tk.Frame(left_panel, bg=self.panel_color)
        btn_analizar_frame.pack(fill=tk.X, pady=(0, 3))
        btn_analizar = tk.Button(btn_analizar_frame, text="📊 ANÁLISIS DE DATOS", 
                                command=self.abrir_analizador,
                                bg="#1f2429", fg="#00ff88", font=("Arial", 10, "bold"),
                                relief=tk.RAISED, bd=1, padx=5, pady=3, width=16)
        btn_analizar.pack()

        tk.Frame(left_panel, height=1, bg=self.border_color).pack(fill=tk.X, pady=3)

        tk.Label(left_panel, text="ESTADO PID", font=("Arial", 11, "bold"), bg=self.panel_color, fg=self.accent_color).pack(pady=(0, 2))
        self.pid_label = tk.Label(left_panel, text="ESTABILIZADO", font=("Arial", 14, "bold"), 
                                 bg=self.panel_color, fg=self.success_color)
        self.pid_label.pack()

        self.error_label = tk.Label(left_panel, text="Error: 0.00 m",
                                   font=("Arial", 12, "bold"), bg=self.panel_color, fg="#ffaa44")
        self.error_label.pack(pady=(2, 0))

        center_panel = tk.Frame(top_frame, bg=self.panel_color, highlightbackground=self.border_color, highlightthickness=1)
        center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 8), ipadx=5, ipady=5)
        center_panel.config(width=280)

        tk.Label(center_panel, text="CONTROL REMOTO", font=("Arial", 12, "bold"), 
                bg=self.panel_color, fg=self.accent_color).pack(pady=(3, 2))

        indicators_frame = tk.Frame(center_panel, bg=self.panel_color)
        indicators_frame.pack(pady=3, padx=3, fill=tk.BOTH, expand=True)

        self.avance_label = self.crear_indicador(indicators_frame, "AVANCE/RETROCESO")
        self.giro_label = self.crear_indicador(indicators_frame, "GIRO (YAW)")
        self.lateral_label = self.crear_indicador(indicators_frame, "LATERAL")
        self.vertical_label = self.crear_indicador(indicators_frame, "EMERGER/SUMERGIR")

        tk.Frame(center_panel, height=1, bg=self.border_color).pack(fill=tk.X, pady=3)

        tk.Label(center_panel, text="CONTROL VERTICAL (PWM µs)", font=("Arial", 10, "bold"), 
                 bg=self.panel_color, fg=self.accent_color).pack(pady=(3, 1))

        info_pwm_frame = tk.Frame(center_panel, bg=self.panel_color)
        info_pwm_frame.pack(fill=tk.X, pady=(0, 2))

        self.lbl_emerger = tk.Label(info_pwm_frame, 
                                   text=f"⬆ EMERGER: {self.PWM_EMERGER} µs", 
                                   font=("Arial", 8, "bold"), bg=self.panel_color, fg="#00ff88")
        self.lbl_emerger.pack(side=tk.LEFT, padx=(5, 0))

        self.lbl_neutro = tk.Label(info_pwm_frame, 
                                  text=f"🎯 NEUTRO: {self.PWM_NEUTRO} µs", 
                                  font=("Arial", 8, "bold"), bg=self.panel_color, fg="#ffaa44")
        self.lbl_neutro.pack(side=tk.LEFT, padx=(10, 0))

        self.lbl_sumergir = tk.Label(info_pwm_frame, 
                                    text=f"⬇ SUMERGIR: {self.PWM_SUMERGER} µs", 
                                    font=("Arial", 8, "bold"), bg=self.panel_color, fg="#ff6b6b")
        self.lbl_sumergir.pack(side=tk.LEFT, padx=(10, 0))

        self.btn_config_pwm = tk.Button(info_pwm_frame, text="⚙️", 
                                       command=self.abrir_pwm_config,
                                       bg="#1f2429", fg="#00b4d8",
                                       font=("Arial", 8, "bold"),
                                       relief=tk.FLAT, bd=0, padx=3, pady=0,
                                       cursor="hand2")
        self.btn_config_pwm.pack(side=tk.RIGHT, padx=(0, 5))

        tk.Label(center_panel, text=" L2 ▲ EMERGER |  R2 ▼ SUMERGIR", 
                 font=("Arial", 9), bg=self.panel_color, fg=self.text_color).pack()

        self.pwm_vertical_bar = tk.Canvas(center_panel, width=200, height=22, bg=self.bg_main,
                                          highlightbackground=self.border_color, highlightthickness=1)
        self.pwm_vertical_bar.pack(pady=(5, 3))
        self.pwm_vertical_bar.create_line(100, 0, 100, 22, fill="#666666", width=1, tags="centro")
        self.pwm_vertical_bar.create_rectangle(0, 0, 100, 22, fill="#444444", tags="bar")

        self.pwm_vertical_label = tk.Label(center_panel, text=f"{self.pwm_vertical} µs", 
                                           font=("Arial", 14, "bold"),
                                           bg=self.panel_color, fg=self.success_color)
        self.pwm_vertical_label.pack(pady=(0, 3))

        pwm_range_frame = tk.Frame(center_panel, bg=self.panel_color)
        pwm_range_frame.pack(fill=tk.X, pady=(0, 3))
        tk.Label(pwm_range_frame, text="1100 µs", font=("Arial", 8), 
                 bg=self.panel_color, fg="#888888").pack(side=tk.LEFT)
        tk.Label(pwm_range_frame, text="1900 µs", font=("Arial", 8), 
                 bg=self.panel_color, fg="#888888").pack(side=tk.RIGHT)

        tk.Frame(center_panel, height=1, bg=self.border_color).pack(fill=tk.X, pady=3)

        potencia_header = tk.Frame(center_panel, bg=self.panel_color)
        potencia_header.pack(fill=tk.X, pady=(3, 1))

        tk.Label(potencia_header, text="POTENCIA GENERAL", font=("Arial", 10, "bold"),
                 bg=self.panel_color, fg=self.accent_color).pack(side=tk.LEFT)

        self.btn_ajuste_potencia = tk.Button(potencia_header, text="⚙️",
                                              command=self.abrir_ajuste_potencia,
                                              bg="#1f2429", fg="#00b4d8",
                                              font=("Arial", 11, "bold"),
                                              relief=tk.FLAT, bd=0, padx=5, pady=0,
                                              cursor="hand2")
        self.btn_ajuste_potencia.pack(side=tk.RIGHT)

        self.potencia_label = tk.Label(center_panel, text=f"{self.potencia}%",
                                       font=("Arial", 20, "bold"), bg=self.panel_color, fg=self.success_color)
        self.potencia_label.pack(pady=(2, 3))

        tk.Frame(center_panel, height=1, bg=self.border_color).pack(fill=tk.X, pady=3)

        compensacion_header = tk.Frame(center_panel, bg=self.panel_color)
        compensacion_header.pack(fill=tk.X, pady=(3, 1))

        tk.Label(compensacion_header, text="COMPENSACIÓN", font=("Arial", 10, "bold"),
                 bg=self.panel_color, fg="#ffaa44").pack(side=tk.LEFT)

        self.btn_compensacion = tk.Button(compensacion_header, text="⚙️ AJUSTE PI", 
                                          command=self.abrir_ventana_pi,
                                          bg="#1f2429", fg="#ffaa44",
                                          font=("Arial", 9, "bold"),
                                          relief=tk.RAISED, bd=1, padx=5, pady=2)
        self.btn_compensacion.pack(side=tk.RIGHT)

        camera_frame = tk.Frame(top_frame, bg=self.panel_color, highlightbackground=self.border_color, highlightthickness=1)
        camera_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(camera_frame, text="CÁMARA", font=("Arial", 12, "bold"), 
                bg=self.panel_color, fg=self.accent_color).pack(pady=(3, 0))

        status_frame = tk.Frame(camera_frame, bg=self.panel_color)
        status_frame.pack(fill=tk.X, padx=10, pady=(2, 0))
        
        self.status_indicator = tk.Canvas(status_frame, width=16, height=16, bg=self.panel_color, highlightthickness=0)
        self.status_indicator.pack(side=tk.LEFT, padx=(0, 8))
        self.status_indicator.create_oval(2, 2, 14, 14, fill="#666666", outline="")
        
        self.status_label = tk.Label(status_frame, text="CONECTANDO...", 
                                     font=("Arial", 10, "bold"), bg=self.panel_color, fg="#888888")
        self.status_label.pack(side=tk.LEFT)

        camera_container = tk.Frame(camera_frame, bg=self.panel_color)
        camera_container.pack(pady=8, padx=8, fill=tk.BOTH, expand=True)

        self.camera_canvas = tk.Canvas(camera_container, width=300, height=270, bg="#000000", 
                                        highlightbackground=self.border_color, highlightthickness=1)
        self.camera_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        barra_container = tk.Frame(camera_container, bg=self.panel_color)
        barra_container.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(5, 0))

        header_frame = tk.Frame(barra_container, bg=self.panel_color)
        header_frame.pack(fill=tk.X, pady=(0, 2))

        tk.Label(header_frame, text="PROF", font=("Arial", 8, "bold"), 
                 bg=self.panel_color, fg=self.accent_color).pack(side=tk.LEFT)

        self.btn_ajuste_profundidad = tk.Button(header_frame, text="⚙️",
                                                 command=self.abrir_ajuste_profundidad_maxima,
                                                 bg="#1f2429", fg="#00b4d8",
                                                 font=("Arial", 8, "bold"),
                                                 relief=tk.FLAT, bd=0, padx=3, pady=0,
                                                 cursor="hand2")
        self.btn_ajuste_profundidad.pack(side=tk.RIGHT)

        marcas_barra_frame = tk.Frame(barra_container, bg=self.panel_color)
        marcas_barra_frame.pack(fill=tk.BOTH, expand=True)

        self.marcas_canvas = tk.Canvas(marcas_barra_frame, width=25, height=270, 
                                        bg="#0a0a1a", highlightthickness=0)
        self.marcas_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.barra_profundidad_canvas = tk.Canvas(marcas_barra_frame, width=20, height=270, 
                                                  bg="#0a0a1a", highlightbackground=self.border_color, 
                                                  highlightthickness=1)
        self.barra_profundidad_canvas.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.profundidad_bar_label = tk.Label(barra_container, text="0.00m", 
                                              font=("Arial", 8, "bold"), bg=self.panel_color, 
                                              fg=self.success_color)
        self.profundidad_bar_label.pack(pady=(1, 0))

        self.dibujar_marcas_profundidad()
        self.dibujar_barra_profundidad()

        self.luz_container = tk.Frame(camera_frame, bg='#1a1a2e', bd=1, relief=tk.RAISED)
        self.luz_container.place(relx=0.89, rely=0.95, anchor='se', width=80, height=42)

        self.luz_led = tk.Canvas(self.luz_container, width=18, height=18, bg='#1a1a2e', highlightthickness=0)
        self.luz_led.pack(side=tk.LEFT, padx=(6, 2), pady=4)
        self.luz_led.create_oval(2, 2, 16, 16, fill="#444444", outline="")
        self.luz_led.create_oval(5, 5, 13, 13, fill="#222222", outline="")

        self.luz_btn = tk.Button(self.luz_container, text="💡", command=self.toggle_luz,
                                 bg="#444444", fg="white", font=("Arial", 14, "bold"),
                                 width=2, height=1, relief=tk.RAISED, bd=1)
        self.luz_btn.pack(side=tk.LEFT, padx=(2, 4), pady=4)

        right_panel = tk.Frame(top_frame, bg=self.panel_color, highlightbackground=self.border_color, highlightthickness=1)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, ipadx=10, ipady=10)

        tk.Label(right_panel, text="INCLINACIÓN", font=("Arial", 11, "bold"), 
                bg=self.panel_color, fg=self.accent_color).pack(pady=(0, 2))
        self.inclinacion_label = tk.Label(right_panel, text="0°", font=("Arial", 32, "bold"), 
                                         bg=self.panel_color, fg=self.success_color)
        self.inclinacion_label.pack()
        self.direccion_label = tk.Label(right_panel, text="✓ NIVELADO", font=("Arial", 12, "bold"), 
                                       bg=self.panel_color, fg=self.accent_color)
        self.direccion_label.pack(pady=(0, 8))

        estab_frame = tk.Frame(right_panel, bg=self.panel_color)
        estab_frame.pack(pady=(0, 8))
        self.estado_estabilidad_label = tk.Label(estab_frame, text="ESTABLE", font=("Arial", 12, "bold"), 
                                                bg=self.panel_color, fg=self.success_color)
        self.estado_estabilidad_label.pack(side=tk.LEFT, padx=(0, 8))
        self.estable_led = tk.Canvas(estab_frame, width=18, height=18, bg=self.panel_color, highlightthickness=0)
        self.estable_led.pack(side=tk.LEFT)
        self.estable_led.create_oval(2, 2, 16, 16, fill="#00ff88", outline="")

        tk.Frame(right_panel, height=1, bg=self.border_color).pack(fill=tk.X, pady=5)

        tk.Label(right_panel, text="PROFUNDIDAD", font=("Arial", 11, "bold"), 
                bg=self.panel_color, fg=self.accent_color).pack(pady=(0, 1))
        self.profundidad_label = tk.Label(right_panel, text="0.00 m", font=("Arial", 20, "bold"), 
                                         bg=self.panel_color, fg="white")
        self.profundidad_label.pack(pady=(0, 3))
        
        tk.Label(right_panel, text="PRESIÓN", font=("Arial", 11, "bold"), 
                bg=self.panel_color, fg=self.accent_color).pack(pady=(0, 1))
        self.presion_label = tk.Label(right_panel, text="1013.2 mbar", font=("Arial", 20, "bold"), 
                                     bg=self.panel_color, fg="white")
        self.presion_label.pack(pady=(0, 3))
        
        tk.Label(right_panel, text="TEMPERATURA", font=("Arial", 11, "bold"), 
                bg=self.panel_color, fg=self.accent_color).pack(pady=(0, 1))
        self.temperatura_label = tk.Label(right_panel, text="25.0 °C", font=("Arial", 20, "bold"), 
                                         bg=self.panel_color, fg="white")
        self.temperatura_label.pack(pady=(0, 3))

        tk.Frame(right_panel, height=1, bg=self.border_color).pack(fill=tk.X, pady=5)

        tk.Label(right_panel, text="DISTANCIA AL SUELO", font=("Arial", 11, "bold"), 
                bg=self.panel_color, fg=self.accent_color).pack(pady=(0, 1))
        self.distancia_suelo_label = tk.Label(right_panel, text="0.0 m", font=("Arial", 20, "bold"), 
                                             bg=self.panel_color, fg="white")
        self.distancia_suelo_label.pack()

        bottom_frame = tk.Frame(main_frame, bg=self.panel_color, highlightbackground=self.border_color, highlightthickness=1)
        bottom_frame.pack(fill=tk.X, pady=(5, 0))

        graficas_frame = tk.Frame(bottom_frame, bg=self.panel_color)
        graficas_frame.pack(fill=tk.X, padx=8, pady=8)

        sonar_frame = tk.Frame(graficas_frame, bg=self.panel_color)
        sonar_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 3))

        sonar_header = tk.Frame(sonar_frame, bg=self.panel_color)
        sonar_header.pack(fill=tk.X, pady=(0, 3))

        tk.Label(sonar_header, text="SENSOR SONAR", font=("Arial", 10, "bold"),
                 bg=self.panel_color, fg=self.accent_color).pack(side=tk.LEFT)

        self.btn_ajuste_sonar = tk.Button(sonar_header, text="⚙️",
                                           command=self.abrir_ajuste_escala,
                                           bg="#1f2429", fg="#00b4d8",
                                           font=("Arial", 10, "bold"),
                                           relief=tk.FLAT, bd=0, padx=5, pady=0,
                                           cursor="hand2")
        self.btn_ajuste_sonar.pack(side=tk.RIGHT)

        self.sonar_canvas = tk.Canvas(sonar_frame, height=180, bg="#0a0a1a",
                                      highlightbackground=self.border_color, highlightthickness=1)
        self.sonar_canvas.pack(fill=tk.BOTH, expand=True)

        error_frame = tk.Frame(graficas_frame, bg=self.panel_color)
        error_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
        tk.Label(error_frame, text="ERROR PID", font=("Arial", 10, "bold"),
                 bg=self.panel_color, fg="#ffaa44").pack(pady=(0, 3))
        self.error_canvas = tk.Canvas(error_frame, height=180, bg="#0a0a1a",
                                      highlightbackground=self.border_color, highlightthickness=1)
        self.error_canvas.pack(fill=tk.BOTH, expand=True)

        salida_frame = tk.Frame(graficas_frame, bg=self.panel_color)
        salida_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(3, 0))
        tk.Label(salida_frame, text="SALIDA DE LAS TURBINAS - PWM", font=("Arial", 10, "bold"),
                 bg=self.panel_color, fg=self.success_color).pack(pady=(0, 3))
        self.salida_canvas = tk.Canvas(salida_frame, height=180, bg="#0a0a1a",
                                       highlightbackground=self.border_color, highlightthickness=1)
        self.salida_canvas.pack(fill=tk.BOTH, expand=True)

    def crear_indicador(self, parent, texto):
        frame = tk.Frame(parent, bg=self.panel_color, relief=tk.RAISED, bd=1)
        frame.pack(fill=tk.X, pady=1)

        tk.Label(frame, text=texto, font=("Arial", 9, "bold"),
                bg=self.panel_color, fg=self.text_color, width=16, anchor='w').pack(side=tk.LEFT, padx=5, pady=3)

        label = tk.Label(frame, text="STOP", font=("Arial", 10, "bold"),
                        bg=self.panel_color, fg=self.success_color, width=14)
        label.pack(side=tk.RIGHT, padx=5, pady=3)
        return label

    def procesar_cola_eventos(self):
        try:
            while True:
                evento = self.cola_eventos.get_nowait()
                if evento[0] == "actualizar_estado_conexion":
                    self.actualizar_estado_conexion(evento[1])
                elif evento[0] == "actualizar_estado_luz":
                    self.actualizar_estado_luz()
                elif evento[0] == "actualizar_datos_sensores":
                    self.actualizar_datos_sensores(evento[1])
                elif evento[0] == "actualizar_indicadores":
                    self.actualizar_indicadores_direccion()
                elif evento[0] == "actualizar_estado_compensacion":
                    self.actualizar_estado_compensacion(evento[1])
        except queue.Empty:
            pass
        finally:
            self.root.after(50, self.procesar_cola_eventos)

    def agregar_evento(self, evento):
        self.cola_eventos.put(evento)

    def setup_joystick(self):
        try:
            pygame.init()
            pygame.joystick.init()

            if pygame.joystick.get_count() > 0:
                self.joystick = pygame.joystick.Joystick(0)
                self.joystick.init()
                self.mando_conectado = True
                print(f"[MANDO] ✅ Mando conectado: {self.joystick.get_name()}")
            else:
                self.mando_conectado = False
                print("[MANDO] ⚠️ No se detectó ningún mando")
        except Exception as e:
            self.mando_conectado = False
            print(f"[MANDO] ❌ Error: {e}")

    def hilo_mando(self):
        ultimo_envio = 0
        
        while self.running:
            if not self.mando_conectado or self.joystick is None:
                time.sleep(0.1)
                continue

            try:
                pygame.event.pump()
                
                raw_avance = self.joystick.get_axis(1)
                raw_lateral = self.joystick.get_axis(0)
                raw_giro = self.joystick.get_axis(2)
                
                self.avance = raw_avance
                self.giro = -raw_giro
                self.lateral = -raw_lateral

                if not self.modo_auto:
                    r2_value = self.joystick.get_axis(5)
                    l2_value = self.joystick.get_axis(4)
                    
                    r2_presionado = r2_value > 0.1
                    l2_presionado = l2_value > 0.1
                    circulo_presionado = self.joystick.get_button(1)
                    
                    if circulo_presionado:
                        self.pwm_vertical = self.PWM_DETENIDO
                        self.estado_detenido = True
                        self.compensacion_salida = 0
                        self.compensacion_integral = 0
                        print(f"[MANDO] 🔴 CÍRCULO PRESIONADO → PWM = 1500µs (DETENIDO)")
                        
                    elif self.estado_detenido and (r2_presionado or l2_presionado):
                        self.estado_detenido = False
                        print(f"[MANDO] ✅ Saliendo de DETENIDO")
                        
                        if r2_presionado:
                            intensidad = (r2_value - 0.1) / 0.9
                            intensidad = min(1.0, max(0.0, intensidad))
                            rango = self.PWM_SUMERGER - self.PWM_NEUTRO
                            offset = int(intensidad * rango)
                            self.pwm_vertical = self.PWM_NEUTRO + offset
                        elif l2_presionado:
                            intensidad = (l2_value - 0.1) / 0.9
                            intensidad = min(1.0, max(0.0, intensidad))
                            rango = self.PWM_NEUTRO - self.PWM_EMERGER
                            offset = int(intensidad * rango)
                            self.pwm_vertical = self.PWM_NEUTRO - offset
                            
                    elif self.estado_detenido:
                        self.pwm_vertical = self.PWM_DETENIDO
                        
                    else:
                        if r2_presionado and not l2_presionado:
                            intensidad = (r2_value - 0.1) / 0.9
                            intensidad = min(1.0, max(0.0, intensidad))
                            rango = self.PWM_SUMERGER - self.PWM_NEUTRO
                            offset = int(intensidad * rango)
                            self.pwm_vertical = self.PWM_NEUTRO + offset
                            
                        elif l2_presionado and not r2_presionado:
                            intensidad = (l2_value - 0.1) / 0.9
                            intensidad = min(1.0, max(0.0, intensidad))
                            rango = self.PWM_NEUTRO - self.PWM_EMERGER
                            offset = int(intensidad * rango)
                            self.pwm_vertical = self.PWM_NEUTRO - offset
                            
                        elif not r2_presionado and not l2_presionado:
                            self.pwm_vertical = self.PWM_NEUTRO
                        else:
                            self.pwm_vertical = self.PWM_NEUTRO
                else:
                    if self.estado_detenido:
                        self.estado_detenido = False
                        print(f"[MANDO] 🔄 Modo auto activo → Resetear estado detenido")

                if self.pwm_vertical > self.PWM_NEUTRO:
                    self.vertical = (self.pwm_vertical - self.PWM_NEUTRO) / 400.0
                elif self.pwm_vertical < self.PWM_NEUTRO:
                    self.vertical = -(self.PWM_NEUTRO - self.pwm_vertical) / 400.0
                else:
                    self.vertical = 0.0

                if self.joystick.get_button(3):
                    tiempo_actual = time.time()
                    if tiempo_actual - self.ultimo_toggle_luz > 0.3:
                        self.toggle_luz()
                        self.ultimo_toggle_luz = tiempo_actual

                if (abs(self.avance) > 0.01 or abs(self.giro) > 0.01 or 
                    abs(self.lateral) > 0.01 or abs(self.vertical) > 0.01):
                    self.agregar_evento(("actualizar_indicadores",))

                ahora = time.time()
                if ahora - ultimo_envio >= 0.05:
                    factor_potencia = self.potencia / 100.0
                    
                    avance_motor = self.avance * factor_potencia
                    giro_motor = self.giro * factor_potencia
                    lateral_motor = self.lateral * factor_potencia
                    vertical_motor = self.vertical * factor_potencia

                    self.enviar_comando_movimiento(avance_motor, giro_motor, lateral_motor, vertical_motor, self.potencia)
                    ultimo_envio = ahora

                time.sleep(0.02)

            except Exception as e:
                print(f"[MANDO] Error: {e}")
                time.sleep(0.1)

    def hilo_pid(self):
        while self.running:
            if self.modo_auto:
                distancia_actual = self.distancia_cm / 100.0
                
                # Verificación de distancia mínima (0.30m para Ping Sonar)
                if distancia_actual < self.DISTANCIA_MINIMA_AUTO and self.distancia_cm > 0:
                    print(f"[PID] ⚠️ Distancia muy baja: {distancia_actual:.2f}m - Manteniendo posición")
                    self.pwm_vertical = self.PWM_NEUTRO
                    self.integral = 0
                    self.pid_salida = 0
                    time.sleep(0.05)
                    continue
                
                if distancia_actual > 0.1:
                    error = self.altura_deseada - distancia_actual
                    
                    ahora = time.time()
                    dt = ahora - self.ultimo_tiempo_pid
                    if dt < 0.001:
                        dt = 0.001
                    self.ultimo_tiempo_pid = ahora
                    
                    p_term = self.kp * error
                    
                    self.integral += error * dt
                    self.integral = max(-50, min(50, self.integral))
                    i_term = self.ki * self.integral
                    
                    if dt > 0:
                        derivada = (error - self.error_anterior) / dt
                    else:
                        derivada = 0
                    self.error_anterior = error
                    d_term = self.kd * derivada
                    
                    salida = p_term + i_term + d_term  # -(p_term + i_term + d_term)  # INVERTIDO
                    salida = max(-1.0, min(1.0, salida))
                    
                    self.pid_salida = salida
                    
                    if salida > 0.02:
                        pwm_offset = int(salida * 400)
                        self.pwm_vertical = self.PWM_NEUTRO - pwm_offset
                        self.pwm_vertical = min(self.PWM_PID_MAX, self.pwm_vertical)
                        self.pwm_vertical = max(self.PWM_PID_MIN, self.pwm_vertical)
                    elif salida < -0.02:
                        pwm_offset = int(abs(salida) * 400)
                        self.pwm_vertical = self.PWM_NEUTRO + pwm_offset
                        self.pwm_vertical = min(self.PWM_PID_MAX, self.pwm_vertical)
                        self.pwm_vertical = max(self.PWM_PID_MIN, self.pwm_vertical)
                    else:
                        self.pwm_vertical = self.PWM_NEUTRO
                        self.integral = 0
                    
                    if self.pwm_vertical > self.PWM_NEUTRO:
                        self.vertical = (self.pwm_vertical - self.PWM_NEUTRO) / 400.0
                    elif self.pwm_vertical < self.PWM_NEUTRO:
                        self.vertical = -(self.PWM_NEUTRO - self.pwm_vertical) / 400.0
                    else:
                        self.vertical = 0.0
                    
                    self.historial_error.append(error)
                    if len(self.historial_error) > 80:
                        self.historial_error.pop(0)
                    
                    self.historial_salida.append(salida)
                    if len(self.historial_salida) > 80:
                        self.historial_salida.pop(0)
                    
                    self.historial_pwm.append(self.pwm_vertical)
                    if len(self.historial_pwm) > 80:
                        self.historial_pwm.pop(0)
                    
                    self.historial_altura.append(distancia_actual)
                    if len(self.historial_altura) > 80:
                        self.historial_altura.pop(0)
                    
                    self.historial_deseada.append(self.altura_deseada)
                    if len(self.historial_deseada) > 80:
                        self.historial_deseada.pop(0)
                else:
                    self.pwm_vertical = self.PWM_NEUTRO
                    self.integral = 0
            
            time.sleep(0.02)

    def enviar_comando_movimiento(self, avance, giro, lateral, vertical, potencia):
        if not self.sock:
            return
        
        try:
            pwm_base = self.pwm_vertical
            pwm_base = max(self.PWM_PID_MIN, min(self.PWM_PID_MAX, pwm_base))
            
            if (pwm_base == self.PWM_DETENIDO or self.estado_detenido) and not self.modo_auto:
                pwm_derecho = self.PWM_DETENIDO
                pwm_izquierdo = self.PWM_DETENIDO
                self.compensacion_salida = 0
                self.compensacion_integral = 0
            else:
                if self.compensacion_activa and abs(self.compensacion_angulo) > 1.0:
                    compensacion = self.compensacion_kp * self.compensacion_angulo
                    compensacion = max(-300, min(300, compensacion))
                    self.compensacion_salida = compensacion
                else:
                    compensacion = 0
                    self.compensacion_integral = 0
                
                pwm_derecho = pwm_base - int(compensacion)
                pwm_izquierdo = pwm_base + int(compensacion)
                
                pwm_derecho = max(1100, min(1900, pwm_derecho))
                pwm_izquierdo = max(1100, min(1900, pwm_izquierdo))
            
            self.historial_pwm_derecho.append(pwm_derecho)
            if len(self.historial_pwm_derecho) > 80:
                self.historial_pwm_derecho.pop(0)
            
            self.historial_pwm_izquierdo.append(pwm_izquierdo)
            if len(self.historial_pwm_izquierdo) > 80:
                self.historial_pwm_izquierdo.pop(0)
            
            comando = {
                'tipo': 'movimiento',
                'avance': round(avance, 3),
                'giro': round(giro, 3),
                'lateral': round(lateral, 3),
                'pwm_derecho': pwm_derecho,
                'pwm_izquierdo': pwm_izquierdo,
                'potencia': potencia
            }
            mensaje = json.dumps(comando) + '\n'
            self.sock.send(mensaje.encode('utf-8'))
            
        except Exception as e:
            print(f"[MOVIMIENTO] ❌ Error: {e}")

    def enviar_comando_luz(self):
        try:
            if self.sock:
                comando = {'tipo': 'luz', 'estado': 1 if self.luz_encendida else 0}
                mensaje = json.dumps(comando) + '\n'
                self.sock.send(mensaje.encode('utf-8'))
        except Exception as e:
            print(f"[LUZ] ❌ Error: {e}")

    def toggle_luz(self):
        self.luz_encendida = not self.luz_encendida
        self.actualizar_estado_luz()
        self.enviar_comando_luz()

    def actualizar_estado_luz(self):
        if hasattr(self, 'luz_btn'):
            if self.luz_encendida:
                self.luz_btn.config(text="💡", bg="#ffaa00", fg="white", relief=tk.SUNKEN)
                self.luz_led.itemconfig(1, fill="#ffaa00")
                self.luz_led.itemconfig(2, fill="#ffdd44")
            else:
                self.luz_btn.config(text="💡", bg="#444444", fg="white", relief=tk.RAISED)
                self.luz_led.itemconfig(1, fill="#444444")
                self.luz_led.itemconfig(2, fill="#222222")

    def actualizar_estado_compensacion(self, activa):
        pass

    def hilo_conexion(self):
        while self.running:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(5.0)
                self.sock.connect((self.bridge_ip, self.bridge_port))
                self.socket_conectado = True
                self.mensaje_reconectando = False
                self.agregar_evento(("actualizar_estado_conexion", True))

                buffer = ""
                while self.running and self.socket_conectado:
                    try:
                        data = self.sock.recv(4096)
                        if data:
                            buffer += data.decode('utf-8', errors='ignore')
                            while '\n' in buffer:
                                linea, buffer = buffer.split('\n', 1)
                                linea = linea.strip()
                                if not linea or not linea.startswith('{'):
                                    continue
                                
                                try:
                                    datos = json.loads(linea)
                                    if 'luz_response' in linea:
                                        estado = datos.get('estado', 0)
                                        self.luz_encendida = (estado == 1)
                                        self.agregar_evento(("actualizar_estado_luz",))
                                        continue
                                    
                                    if 'datos_sensores' in linea:
                                        if 'presion' in datos:
                                            p = datos['presion']
                                            self.presion_mbar = p.get('mbar', 1013.25)
                                            self.profundidad_m = p.get('profundidad_m', 0.0)
                                            self.temperatura_c = p.get('temperatura_c', 25.0)
                                            self.sensor_presion_ok = p.get('ok', False)
                                        
                                        if 'sonar' in datos:
                                            distancia = datos['sonar'].get('distancia_cm', -1)
                                            if distancia > 0:
                                                distancia_filtrada = self.filtrar_sonar(distancia)
                                                self.distancia_cm = distancia_filtrada
                                                self.confianza = datos['sonar'].get('confianza', 0)
                                                self.historial.append(self.distancia_cm)
                                                if len(self.historial) > 80:
                                                    self.historial.pop(0)
                                        
                                        if 'mpu' in datos:
                                            self.ay = datos['mpu'].get('ay', 0.0)
                                            try:
                                                angulo = math.degrees(math.asin(max(-0.99, min(0.99, self.ay))))
                                                self.compensacion_angulo = angulo
                                            except:
                                                pass
                                        
                                        if 'luz' in datos:
                                            estado_luz = 1 if datos['luz'].get('encendida', False) else 0
                                            if estado_luz != (1 if self.luz_encendida else 0):
                                                self.luz_encendida = (estado_luz == 1)
                                                self.agregar_evento(("actualizar_estado_luz",))
                                        
                                        self.agregar_evento(("actualizar_datos_sensores", datos))
                                        continue

                                    if 'distancia' in datos:
                                        distancia = datos.get('distancia', -1)
                                        if distancia > 0:
                                            distancia_filtrada = self.filtrar_sonar(distancia)
                                            self.distancia_cm = distancia_filtrada
                                            self.confianza = datos.get('confianza', 0)
                                            self.historial.append(self.distancia_cm)
                                            if len(self.historial) > 80:
                                                self.historial.pop(0)
                                            self.agregar_evento(("actualizar_datos_sensores", datos))
                                    
                                    if 'ay' in datos:
                                        self.ay = datos.get('ay', 0.0)
                                        try:
                                            angulo = math.degrees(math.asin(max(-0.99, min(0.99, self.ay))))
                                            self.compensacion_angulo = angulo
                                        except:
                                            pass
                                    
                                    if 'presion' in datos:
                                        p = datos['presion']
                                        self.presion_mbar = p.get('mbar', 1013.25)
                                        self.profundidad_m = p.get('profundidad_m', 0.0)
                                        self.temperatura_c = p.get('temperatura_c', 25.0)
                                        self.sensor_presion_ok = p.get('ok', False)
                                        
                                except json.JSONDecodeError:
                                    pass
                        else:
                            break
                    except socket.timeout:
                        continue
                    except Exception as e:
                        print(f"[CONEXION] Error: {e}")
                        break

                if self.sock:
                    self.sock.close()
                    self.sock = None
                    self.socket_conectado = False

                self.agregar_evento(("actualizar_estado_conexion", False))
                self.mensaje_reconectando = True
                time.sleep(2)

            except Exception as e:
                print(f"[CONEXION] Error de conexión: {e}")
                self.socket_conectado = False
                if self.sock:
                    try:
                        self.sock.close()
                    except:
                        pass
                    self.sock = None
                self.agregar_evento(("actualizar_estado_conexion", False))
                self.mensaje_reconectando = True
                time.sleep(3)

    def actualizar_estado_conexion(self, conectado):
        if conectado:
            self.mensaje_reconectando = False
            self.status_indicator.itemconfig(1, fill="#00ff88")
            self.status_label.config(text="CONECTADO", fg="#00ff88")
        else:
            self.mensaje_reconectando = True
            self.status_indicator.itemconfig(1, fill="#ff6b6b")
            self.status_label.config(text="DESCONECTADO", fg="#ff6b6b")

    def actualizar_datos_sensores(self, datos):
        if 'distancia' in datos:
            distancia = datos['distancia']
            if distancia > 0:
                self.distancia_suelo_label.config(text=f"{distancia/100.0:.2f} m")
        
        if 'ay' in datos:
            try:
                angulo = math.degrees(math.asin(max(-0.99, min(0.99, datos['ay']))))
                self.inclinacion_label.config(text=f"{angulo:.0f}°")
                
                if angulo > 5:
                    self.direccion_label.config(text="INCLINADO DERECHA ➡")
                    self.inclinacion_label.config(fg="#ffaa44")
                    self.estable_led.itemconfig(1, fill=self.warning_color)
                    self.estado_estabilidad_label.config(text="PELIGRO", fg=self.warning_color)
                elif angulo < -5:
                    self.direccion_label.config(text="⬅ INCLINADO IZQUIERDA")
                    self.inclinacion_label.config(fg="#ffaa44")
                    self.estable_led.itemconfig(1, fill=self.warning_color)
                    self.estado_estabilidad_label.config(text="PELIGRO", fg=self.warning_color)
                else:
                    self.direccion_label.config(text="✓ NIVELADO")
                    self.inclinacion_label.config(fg=self.success_color)
                    self.estable_led.itemconfig(1, fill=self.success_color)
                    self.estado_estabilidad_label.config(text="ESTABLE", fg=self.success_color)
            except:
                pass
        
        if 'presion' in datos:
            p = datos['presion']
            if p.get('ok', False):
                self.profundidad_label.config(text=f"{p.get('profundidad_m', 0):.2f} m")
                self.presion_label.config(text=f"{p.get('mbar', 0):.1f} mbar")
                self.temperatura_label.config(text=f"{p.get('temperatura_c', 0):.1f} °C")

    def toggle_modo_auto(self):
        self.modo_auto = not self.modo_auto
        
        if self.modo_auto:
            self.estado_detenido = False
            self.auto_btn.config(text="ACTIVADO", bg="#00ff88", fg="black")
            self.auto_led.itemconfig(1, fill="#00ff88")
            self.pid_label.config(text="PID ACTIVO", fg="#ffaa00")
            
            self.error_anterior = 0
            self.integral = 0
            self.pid_salida = 0
            self.ultimo_tiempo_pid = time.time()
            self.pwm_vertical = self.PWM_NEUTRO
            self.vertical = 0.0
            
            print(f"🔄 MODO AUTOMÁTICO ACTIVADO - Altura: {self.altura_deseada:.2f}m")
        else:
            self.estado_detenido = False
            self.auto_btn.config(text="DESACTIVADO", bg="#444444", fg="white")
            self.auto_led.itemconfig(1, fill="#444444")
            self.pid_label.config(text="ESTABILIZADO", fg=self.success_color)
            
            self.pwm_vertical = self.PWM_NEUTRO
            self.vertical = 0.0
            self.integral = 0
            self.pid_salida = 0
            self.error_anterior = 0
            self.error_label.config(text="Error: --- m", fg="#666666")
            
            self.enviar_comando_movimiento(0, 0, 0, 0, self.potencia)
            
            print(f"🔄 MODO AUTOMÁTICO DESACTIVADO")

    def set_manual_height(self):
        try:
            valor = float(self.depth_entry.get())
            if 0 <= valor <= 50:
                self.altura_deseada = valor
                self.altura_deseada_label.config(text=f"{self.altura_deseada:.1f} m")
                self.historial_deseada = [self.altura_deseada] * 80
                self.error_anterior = 0
                self.integral = 0
                self.depth_entry.delete(0, tk.END)
                print(f"[PID] Altura deseada: {self.altura_deseada:.2f}m")
            else:
                messagebox.showerror("Error", "Altura entre 0 y 50 metros")
                self.depth_entry.delete(0, tk.END)
        except ValueError:
            messagebox.showerror("Error", "Ingrese un número válido")
            self.depth_entry.delete(0, tk.END)

    def abrir_ajuste_potencia(self):
        ventana = tk.Toplevel(self.root)
        ventana.title("Ajustar Potencia General")
        ventana.geometry("300x200")
        ventana.configure(bg="#0a0a1a")
        ventana.resizable(False, False)

        tk.Label(ventana, text="AJUSTE DE POTENCIA GENERAL",
                 font=("Arial", 14, "bold"), bg="#0a0a1a", fg="#00b4d8").pack(pady=(15, 5))

        tk.Label(ventana, text="Potencia para motores de desplazamiento",
                 font=("Arial", 10), bg="#0a0a1a", fg="#888888").pack(pady=(0, 15))

        frame_entry = tk.Frame(ventana, bg="#0d1117", highlightbackground="#1f2429", highlightthickness=2)
        frame_entry.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        tk.Label(frame_entry, text=f"Potencia actual: {self.potencia}%",
                 font=("Arial", 11, "bold"), bg="#0d1117", fg="#00ff88").pack(pady=(10, 5))

        tk.Label(frame_entry, text="Nueva potencia (0-100%):",
                 font=("Arial", 10), bg="#0d1117", fg="#888888").pack(pady=(5, 2))

        potencia_var = tk.StringVar(value=f"{self.potencia}")
        potencia_entry = tk.Entry(frame_entry, textvariable=potencia_var,
                                 font=("Arial", 14), width=10, justify='center',
                                 bg="#1a1a2e", fg="#00b4d8", insertbackground="#00b4d8",
                                 relief=tk.FLAT, highlightbackground="#1f2429", highlightthickness=1)
        potencia_entry.pack(pady=(5, 10))
        potencia_entry.focus_set()
        potencia_entry.select_range(0, tk.END)

        btn_frame = tk.Frame(frame_entry, bg="#0d1117")
        btn_frame.pack(pady=5)

        def aplicar_potencia():
            try:
                valor = int(potencia_var.get())
                if 0 <= valor <= 100:
                    self.potencia = valor
                    self.potencia_label.config(text=f"{self.potencia}%")
                    ventana.destroy()
                    print(f"[POTENCIA] Potencia general ajustada a {self.potencia}%")
                else:
                    potencia_var.set(f"{self.potencia}")
                    for widget in frame_entry.winfo_children():
                        if isinstance(widget, tk.Label) and "⚠️" in widget.cget("text"):
                            widget.destroy()
                    tk.Label(frame_entry, text="⚠️ Valor debe estar entre 0 y 100",
                            font=("Arial", 9), bg="#0d1117", fg="#ff6b6b").pack(pady=(0, 5))
            except ValueError:
                potencia_var.set(f"{self.potencia}")
                for widget in frame_entry.winfo_children():
                    if isinstance(widget, tk.Label) and "⚠️" in widget.cget("text"):
                        widget.destroy()
                tk.Label(frame_entry, text="⚠️ Ingrese un número válido",
                        font=("Arial", 9), bg="#0d1117", fg="#ff6b6b").pack(pady=(0, 5))

        def cerrar_ventana():
            ventana.destroy()

        tk.Button(btn_frame, text="Aplicar", command=aplicar_potencia,
                  bg="#1f2429", fg="#00ff88", font=("Arial", 10, "bold"),
                  relief=tk.RAISED, bd=2, padx=20, pady=5).pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text="Cancelar", command=cerrar_ventana,
                  bg="#444444", fg="white", font=("Arial", 10, "bold"),
                  relief=tk.RAISED, bd=2, padx=20, pady=5).pack(side=tk.LEFT, padx=5)

        potencia_entry.bind('<Return>', lambda event: aplicar_potencia())
        potencia_entry.bind('<Escape>', lambda event: cerrar_ventana())

    def abrir_ajuste_escala(self):
        ventana = tk.Toplevel(self.root)
        ventana.title("Ajustar Escala - Sonar")
        ventana.geometry("300x220")
        ventana.configure(bg="#0a0a1a")
        ventana.resizable(False, False)

        tk.Label(ventana, text="AJUSTE DE ESCALA",
                 font=("Arial", 14, "bold"), bg="#0a0a1a", fg="#00b4d8").pack(pady=(15, 5))

        tk.Label(ventana, text="Gráfica del Sensor Sonar",
                 font=("Arial", 10), bg="#0a0a1a", fg="#888888").pack(pady=(0, 15))

        frame_entry = tk.Frame(ventana, bg="#0d1117", highlightbackground="#1f2429", highlightthickness=2)
        frame_entry.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        tk.Label(frame_entry, text=f"Escala actual: {self.escala_sonar:.1f} m",
                 font=("Arial", 11, "bold"), bg="#0d1117", fg="#00ff88").pack(pady=(10, 5))

        tk.Label(frame_entry, text="Nueva escala (1-100 metros):",
                 font=("Arial", 10), bg="#0d1117", fg="#888888").pack(pady=(5, 2))

        escala_var = tk.StringVar(value=f"{self.escala_sonar:.1f}")
        escala_entry = tk.Entry(frame_entry, textvariable=escala_var,
                               font=("Arial", 14), width=10, justify='center',
                               bg="#1a1a2e", fg="#00b4d8", insertbackground="#00b4d8",
                               relief=tk.FLAT, highlightbackground="#1f2429", highlightthickness=1)
        escala_entry.pack(pady=(5, 10))
        escala_entry.focus_set()
        escala_entry.select_range(0, tk.END)

        btn_frame = tk.Frame(frame_entry, bg="#0d1117")
        btn_frame.pack(pady=5)

        def aplicar_escala():
            try:
                valor = float(escala_var.get())
                if 1.0 <= valor <= 100.0:
                    self.escala_sonar = valor
                    ventana.destroy()
                    print(f"[ESCALA] Sonar ajustado a {self.escala_sonar:.1f} metros")
                else:
                    escala_var.set(f"{self.escala_sonar:.1f}")
                    for widget in frame_entry.winfo_children():
                        if isinstance(widget, tk.Label) and "⚠️" in widget.cget("text"):
                            widget.destroy()
                    tk.Label(frame_entry, text="⚠️ Valor debe estar entre 1 y 100",
                            font=("Arial", 9), bg="#0d1117", fg="#ff6b6b").pack(pady=(0, 5))
            except ValueError:
                escala_var.set(f"{self.escala_sonar:.1f}")
                for widget in frame_entry.winfo_children():
                    if isinstance(widget, tk.Label) and "⚠️" in widget.cget("text"):
                        widget.destroy()
                tk.Label(frame_entry, text="⚠️ Ingrese un número válido",
                        font=("Arial", 9), bg="#0d1117", fg="#ff6b6b").pack(pady=(0, 5))

        def cerrar_ventana():
            ventana.destroy()

        tk.Button(btn_frame, text="Aplicar", command=aplicar_escala,
                  bg="#1f2429", fg="#00ff88", font=("Arial", 10, "bold"),
                  relief=tk.RAISED, bd=2, padx=20, pady=5).pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text="Cancelar", command=cerrar_ventana,
                  bg="#444444", fg="white", font=("Arial", 10, "bold"),
                  relief=tk.RAISED, bd=2, padx=20, pady=5).pack(side=tk.LEFT, padx=5)

        escala_entry.bind('<Return>', lambda event: aplicar_escala())
        escala_entry.bind('<Escape>', lambda event: cerrar_ventana())

    def abrir_ajuste_profundidad_maxima(self):
        ventana = tk.Toplevel(self.root)
        ventana.title("Ajustar Profundidad Máxima - Barra")
        ventana.geometry("320x220")
        ventana.configure(bg="#0a0a1a")
        ventana.resizable(False, False)

        tk.Label(ventana, text="AJUSTE DE PROFUNDIDAD MÁXIMA",
                 font=("Arial", 14, "bold"), bg="#0a0a1a", fg="#00b4d8").pack(pady=(15, 5))

        tk.Label(ventana, text="Escala de la barra de profundidad",
                 font=("Arial", 10), bg="#0a0a1a", fg="#888888").pack(pady=(0, 15))

        frame_entry = tk.Frame(ventana, bg="#0d1117", highlightbackground="#1f2429", highlightthickness=2)
        frame_entry.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        tk.Label(frame_entry, text=f"Profundidad máxima actual: {self.profundidad_maxima:.1f} m",
                 font=("Arial", 11, "bold"), bg="#0d1117", fg="#00ff88").pack(pady=(10, 5))

        tk.Label(frame_entry, text="Nueva profundidad máxima (1-100 metros):",
                 font=("Arial", 10), bg="#0d1117", fg="#888888").pack(pady=(5, 2))

        profundidad_var = tk.StringVar(value=f"{self.profundidad_maxima:.1f}")
        profundidad_entry = tk.Entry(frame_entry, textvariable=profundidad_var,
                                     font=("Arial", 14), width=10, justify='center',
                                     bg="#1a1a2e", fg="#00b4d8", insertbackground="#00b4d8",
                                     relief=tk.FLAT, highlightbackground="#1f2429", highlightthickness=1)
        profundidad_entry.pack(pady=(5, 10))
        profundidad_entry.focus_set()
        profundidad_entry.select_range(0, tk.END)

        btn_frame = tk.Frame(frame_entry, bg="#0d1117")
        btn_frame.pack(pady=5)

        def aplicar_profundidad():
            try:
                valor = float(profundidad_var.get())
                if 1.0 <= valor <= 100.0:
                    self.profundidad_maxima = valor
                    ventana.destroy()
                    print(f"[PROFUNDIDAD] Profundidad máxima ajustada a {self.profundidad_maxima:.1f} metros")
                    self.dibujar_marcas_profundidad()
                    self.dibujar_barra_profundidad()
                else:
                    profundidad_var.set(f"{self.profundidad_maxima:.1f}")
                    for widget in frame_entry.winfo_children():
                        if isinstance(widget, tk.Label) and "⚠️" in widget.cget("text"):
                            widget.destroy()
                    tk.Label(frame_entry, text="⚠️ Valor debe estar entre 1 y 100",
                            font=("Arial", 9), bg="#0d1117", fg="#ff6b6b").pack(pady=(0, 5))
            except ValueError:
                profundidad_var.set(f"{self.profundidad_maxima:.1f}")
                for widget in frame_entry.winfo_children():
                    if isinstance(widget, tk.Label) and "⚠️" in widget.cget("text"):
                        widget.destroy()
                tk.Label(frame_entry, text="⚠️ Ingrese un número válido",
                        font=("Arial", 9), bg="#0d1117", fg="#ff6b6b").pack(pady=(0, 5))

        def cerrar_ventana():
            ventana.destroy()

        tk.Button(btn_frame, text="Aplicar", command=aplicar_profundidad,
                  bg="#1f2429", fg="#00ff88", font=("Arial", 10, "bold"),
                  relief=tk.RAISED, bd=2, padx=20, pady=5).pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text="Cancelar", command=cerrar_ventana,
                  bg="#444444", fg="white", font=("Arial", 10, "bold"),
                  relief=tk.RAISED, bd=2, padx=20, pady=5).pack(side=tk.LEFT, padx=5)

        profundidad_entry.bind('<Return>', lambda event: aplicar_profundidad())
        profundidad_entry.bind('<Escape>', lambda event: cerrar_ventana())

    def actualizar_indicadores_direccion(self):
        if abs(self.avance) < 0.1:
            self.avance_label.config(text="STOP", fg=self.success_color)
        elif self.avance > 0:
            self.avance_label.config(text="⬇ RETROCESO", fg=self.accent_color)
        else:
            self.avance_label.config(text="⬆ AVANCE", fg=self.accent_color)

        if abs(self.giro) < 0.1:
            self.giro_label.config(text="STOP", fg=self.success_color)
        elif self.giro > 0:
            self.giro_label.config(text="↺ IZQUIERDA", fg=self.accent_color)
        else:
            self.giro_label.config(text="↻ DERECHA", fg=self.accent_color)

        if abs(self.lateral) < 0.1:
            self.lateral_label.config(text="STOP", fg=self.success_color)
        elif self.lateral > 0:
            self.lateral_label.config(text="⬅ IZQUIERDA", fg=self.accent_color)
        else:
            self.lateral_label.config(text="➡ DERECHA", fg=self.accent_color)

        if self.pwm_vertical == self.PWM_DETENIDO:
            self.vertical_label.config(text="⏹ DETENIDO", fg="#ff6b6b")
        elif self.pwm_vertical > self.PWM_NEUTRO + 5:
            self.vertical_label.config(text=f"⬇ SUMERGIR ({self.pwm_vertical})", fg="#ff6b6b")
        elif self.pwm_vertical < self.PWM_NEUTRO - 5:
            self.vertical_label.config(text=f"⬆ EMERGER ({self.pwm_vertical})", fg="#00ff88")
        else:
            self.vertical_label.config(text=f"✓ NEUTRO", fg="#ffaa44")

    def conectar_camara(self):
        try:
            self.video_client = VideoClient(self.bridge_ip, 8555)
            if self.video_client.connect():
                self.camera_connected = True
                self.camera_running = True
                print("[CÁMARA] ✅ Conectada")
                threading.Thread(target=self.recibir_video, daemon=True).start()
            else:
                self.camera_connected = False
        except Exception as e:
            print(f"[CÁMARA] Error: {e}")
            self.camera_connected = False

    def recibir_video(self):
        while self.running and self.camera_connected:
            try:
                if self.video_client:
                    frame = self.video_client.receive_frame()
                    if frame is not None:
                        self.frame = frame
                time.sleep(0.01)
            except Exception as e:
                print(f"[CÁMARA] Error: {e}")
                time.sleep(0.1)

    def mostrar_camara(self):
        if self.frame is not None and hasattr(self, 'camera_canvas'):
            try:
                w = self.camera_canvas.winfo_width()
                h = self.camera_canvas.winfo_height()
                if w <= 1:
                    w = 300
                    h = 270

                frame_resized = cv2.resize(self.frame, (w, h))
                frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                
                if self.mensaje_reconectando:
                    cv2.putText(frame_rgb, "RECONECTANDO...", (20, 35), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                img = Image.fromarray(frame_rgb)
                imgtk = ImageTk.PhotoImage(image=img)

                self.camera_canvas.delete("all")
                self.camera_canvas.create_image(0, 0, anchor=tk.NW, image=imgtk)
                self.camera_canvas.image = imgtk

            except Exception as e:
                pass

    def dibujar_marcas_profundidad(self):
        if not hasattr(self, 'marcas_canvas'):
            return
        
        self.marcas_canvas.delete("all")
        
        w = self.marcas_canvas.winfo_width()
        h = self.marcas_canvas.winfo_height()
        
        if w <= 1:
            w = 25
        if h <= 1:
            h = 270
        
        profundidad_max = self.profundidad_maxima
        margen = 5
        
        if profundidad_max <= 5:
            paso = 0.5
        elif profundidad_max <= 10:
            paso = 1
        elif profundidad_max <= 25:
            paso = 2
        elif profundidad_max <= 50:
            paso = 5
        elif profundidad_max <= 100:
            paso = 10
        else:
            paso = 20
        
        if profundidad_max / paso > 20:
            paso = paso * 2
        
        marcas = []
        marca = 0
        while marca <= profundidad_max:
            marcas.append(marca)
            marca += paso
        
        if marcas[-1] != profundidad_max:
            marcas.append(profundidad_max)
        
        for marca in marcas:
            y_marca = margen + int((marca / profundidad_max) * (h - 2 * margen))
            self.marcas_canvas.create_line(w-6, y_marca, w-2, y_marca, fill="#666666", width=1)
            self.marcas_canvas.create_text(2, y_marca, text=f"{marca:.0f}m", 
                                           fill="#888888", font=("Arial", 6), anchor="w")

    def dibujar_barra_profundidad(self):
        if not hasattr(self, 'barra_profundidad_canvas'):
            return
        
        self.barra_profundidad_canvas.delete("all")
        
        w = self.barra_profundidad_canvas.winfo_width()
        h = self.barra_profundidad_canvas.winfo_height()
        
        if w <= 1:
            w = 20
        if h <= 1:
            h = 270
        
        profundidad_max = self.profundidad_maxima
        margen = 5
        
        self.barra_profundidad_canvas.create_rectangle(2, 2, w-2, h-2, fill="#0a0a1a", outline="#1f2429")
        
        profundidad_actual = min(self.profundidad_m, profundidad_max)
        porcentaje = profundidad_actual / profundidad_max if profundidad_max > 0 else 0
        y_pos = margen + int(porcentaje * (h - 2 * margen))
        
        if porcentaje > 0.01:
            fill_height = int(porcentaje * (h - 2 * margen))
            self.barra_profundidad_canvas.create_rectangle(4, h - margen - fill_height, w-4, h - margen, 
                                                           fill="#0077be", outline="")
        
        if profundidad_actual > 0.01:
            radio = 4
            self.barra_profundidad_canvas.create_oval(w//2 - radio, y_pos - radio, 
                                                       w//2 + radio, y_pos + radio, 
                                                       fill="#00ff88", outline="#00ff88", width=1)
            self.barra_profundidad_canvas.create_line(0, y_pos, w//2 - radio, y_pos, fill="#00ff88", width=1)
            self.profundidad_bar_label.config(text=f"{profundidad_actual:.2f}m", fg="#00ff88")
        else:
            self.barra_profundidad_canvas.create_oval(w//2 - 3, margen + 2, w//2 + 3, margen + 8, 
                                                       fill="#ffaa44", outline="#ffaa44", width=1)
            self.profundidad_bar_label.config(text="0.00m", fg="#ffaa44")

    def dibujar_sonar(self):
        if not hasattr(self, 'sonar_canvas'):
            return
        self.sonar_canvas.delete("all")
        w = self.sonar_canvas.winfo_width()
        h = self.sonar_canvas.winfo_height()
        if w <= 1:
            w = 300
            h = 180

        margen_izquierdo = 35
        margen_derecho = 10
        margen_superior = 20
        margen_inferior = 30

        draw_w = w - margen_izquierdo - margen_derecho
        draw_h = h - margen_superior - margen_inferior

        max_metros = self.escala_sonar

        self.sonar_canvas.create_line(margen_izquierdo, margen_superior, margen_izquierdo, h - margen_inferior, 
                                      fill="#666666", width=1)
        self.sonar_canvas.create_line(margen_izquierdo, h - margen_inferior, w - margen_derecho, h - margen_inferior, 
                                      fill="#666666", width=2)

        num_marcas_y = 5
        for i in range(num_marcas_y + 1):
            valor = max_metros - (i / num_marcas_y) * max_metros
            y_pos = margen_superior + (i / num_marcas_y) * draw_h
            self.sonar_canvas.create_text(margen_izquierdo - 5, y_pos, 
                                         text=f"{valor:.1f}", fill="#888888", font=("Arial", 9), anchor="e")
            if i > 0 and i < num_marcas_y:
                self.sonar_canvas.create_line(margen_izquierdo, y_pos, w - margen_derecho, y_pos, 
                                              fill="#333333", width=1, dash=(2, 4))

        self.sonar_canvas.create_text(w // 2, h - 5, text="TIEMPO (s)", 
                                     fill="#00b4d8", font=("Arial", 10, "bold"))
        
        self.sonar_canvas.create_text(5, 10, text="DISTANCIA (m)", fill="#888888", font=("Arial", 9), anchor="nw")

        if self.modo_auto and self.altura_deseada <= max_metros:
            y_deseada = margen_superior + draw_h - (self.altura_deseada / max_metros) * draw_h
            self.sonar_canvas.create_line(margen_izquierdo, y_deseada, w - margen_derecho, y_deseada, 
                                          fill="#ffaa44", width=2, dash=(5, 5))
            self.sonar_canvas.create_text(w - margen_derecho - 5, y_deseada - 5, 
                                         text=f"Deseada: {self.altura_deseada:.1f}m", 
                                         fill="#ffaa44", font=("Arial", 8), anchor="ne")

        if len(self.historial) > 1:
            step = draw_w / len(self.historial)
            points = []
            for i, valor_cm in enumerate(self.historial):
                x = margen_izquierdo + i * step
                valor_m = min(valor_cm / 100.0, max_metros)
                y = margen_superior + draw_h - (valor_m / max_metros) * draw_h
                points.append((x, y))
            
            for i in range(len(points) - 1):
                self.sonar_canvas.create_line(points[i][0], points[i][1], points[i+1][0], points[i+1][1],
                                             fill=self.accent_color, width=2)

        if self.distancia_cm > 0:
            self.sonar_canvas.create_text(w - 5, h - 5, 
                                         text=f"{self.distancia_cm/100.0:.2f} m",
                                         fill=self.accent_color, font=("Arial", 10, "bold"), anchor="se")
        else:
            self.sonar_canvas.create_text(w - 5, h - 5, text="--- m",
                                         fill="#666666", font=("Arial", 10, "bold"), anchor="se")

    def dibujar_error(self):
        if not hasattr(self, 'error_canvas'):
            return
        self.error_canvas.delete("all")
        w = self.error_canvas.winfo_width()
        h = self.error_canvas.winfo_height()
        if w <= 1:
            w = 300
            h = 180

        margen_izquierdo = 35
        margen_derecho = 10
        margen_superior = 20
        margen_inferior = 30

        draw_w = w - margen_izquierdo - margen_derecho
        draw_h = h - margen_superior - margen_inferior

        center_y = margen_superior + draw_h // 2
        max_error = 1.0

        self.error_canvas.create_line(margen_izquierdo, margen_superior, margen_izquierdo, h - margen_inferior, 
                                      fill="#666666", width=1)
        self.error_canvas.create_line(margen_izquierdo, h - margen_inferior, w - margen_derecho, h - margen_inferior, 
                                      fill="#666666", width=2)

        self.error_canvas.create_line(margen_izquierdo, center_y, w - margen_derecho, center_y, 
                                      fill="#444444", width=1, dash=(4, 4))

        valores_y = [1.0, 0.5, 0.0, -0.5, -1.0]
        for valor in valores_y:
            y_pos = center_y - (valor / max_error) * (draw_h / 2)
            if margen_superior <= y_pos <= h - margen_inferior:
                self.error_canvas.create_text(margen_izquierdo - 5, y_pos, 
                                             text=f"{valor:+.1f}", fill="#888888", font=("Arial", 9), anchor="e")

        self.error_canvas.create_text(w // 2, h - 5, text="TIEMPO (s)", 
                                     fill="#ffaa44", font=("Arial", 10, "bold"))
        
        self.error_canvas.create_text(5, 10, text="Error (m)", fill="#888888", font=("Arial", 9), anchor="nw")

        if len(self.historial_error) > 1 and self.modo_auto:
            step = draw_w / len(self.historial_error)
            points = []
            for i, valor in enumerate(self.historial_error):
                x = margen_izquierdo + i * step
                valor_norm = max(-max_error, min(max_error, valor))
                y = center_y - (valor_norm / max_error) * (draw_h / 2)
                points.append((x, y))
            
            for i in range(len(points) - 1):
                self.error_canvas.create_line(points[i][0], points[i][1], points[i+1][0], points[i+1][1],
                                             fill="#ffaa44", width=2)

        if len(self.historial_error) > 0 and self.modo_auto:
            error_actual = self.historial_error[-1]
            color = "#00ff88" if abs(error_actual) < 0.05 else "#ffaa44" if abs(error_actual) < 0.2 else "#ff6b6b"
            self.error_canvas.create_text(w - 5, h - 5, text=f"{error_actual:+.2f} m",
                                         fill=color, font=("Arial", 10, "bold"), anchor="se")
        else:
            self.error_canvas.create_text(w - 5, h - 5, text="--- m",
                                         fill="#666666", font=("Arial", 10, "bold"), anchor="se")

    def dibujar_salida_pid(self):
        if not hasattr(self, 'salida_canvas'):
            return
        self.salida_canvas.delete("all")
        w = self.salida_canvas.winfo_width()
        h = self.salida_canvas.winfo_height()
        if w <= 1:
            w = 300
            h = 180

        margen_izquierdo = 40
        margen_derecho = 10
        margen_superior = 20
        margen_inferior = 30

        draw_w = w - margen_izquierdo - margen_derecho
        draw_h = h - margen_superior - margen_inferior

        pwm_min = 1100
        pwm_max = 1900

        self.salida_canvas.create_line(margen_izquierdo, margen_superior, margen_izquierdo, h - margen_inferior, 
                                       fill="#666666", width=1)
        self.salida_canvas.create_line(margen_izquierdo, h - margen_inferior, w - margen_derecho, h - margen_inferior, 
                                       fill="#666666", width=2)

        y_centro = margen_superior + draw_h // 2
        self.salida_canvas.create_line(margen_izquierdo, y_centro, w - margen_derecho, y_centro, 
                                       fill="#444444", width=1, dash=(4, 4))

        self.salida_canvas.create_line(margen_izquierdo, margen_superior, w - margen_derecho, margen_superior, 
                                       fill="#333333", width=1, dash=(2, 4))
        self.salida_canvas.create_line(margen_izquierdo, h - margen_inferior, w - margen_derecho, h - margen_inferior, 
                                       fill="#333333", width=1, dash=(2, 4))

        valores_pwm = [1900, 1700, 1500, 1300, 1100]
        for valor in valores_pwm:
            y_pos = margen_superior + (1 - (valor - pwm_min) / (pwm_max - pwm_min)) * draw_h
            if margen_superior <= y_pos <= h - margen_inferior:
                self.salida_canvas.create_text(margen_izquierdo - 5, y_pos, 
                                             text=f"{valor}", fill="#888888", font=("Arial", 8), anchor="e")

        self.salida_canvas.create_text(w // 2, h - 5, text="TIEMPO (s)", 
                                     fill=self.success_color, font=("Arial", 9, "bold"))
        
        self.salida_canvas.create_text(5, 10, text="PWM (µs)", fill="#888888", font=("Arial", 8), anchor="nw")

        self.salida_canvas.create_line(w - 155, 15, w - 140, 15, fill="#ffaa44", width=2)
        self.salida_canvas.create_text(w - 135, 15, text="IZQUIERDA", 
                                      fill="#ffaa44", font=("Arial", 7, "bold"), anchor="w")
        
        self.salida_canvas.create_line(w - 155, 28, w - 140, 28, fill="#00b4d8", width=2)
        self.salida_canvas.create_text(w - 135, 28, text="DERECHA", 
                                      fill="#00b4d8", font=("Arial", 7, "bold"), anchor="w")

        if hasattr(self, 'compensacion_salida'):
            compensacion = self.compensacion_salida
        else:
            compensacion = 0
        
        pwm_base = self.pwm_vertical
        
        pwm_derecho = pwm_base - int(compensacion)
        pwm_izquierdo = pwm_base + int(compensacion)
        
        pwm_derecho = max(1100, min(1900, pwm_derecho))
        pwm_izquierdo = max(1100, min(1900, pwm_izquierdo))

        if not hasattr(self, 'historial_pwm_derecho'):
            self.historial_pwm_derecho = [self.PWM_NEUTRO] * 80
        if not hasattr(self, 'historial_pwm_izquierdo'):
            self.historial_pwm_izquierdo = [self.PWM_NEUTRO] * 80
        
        self.historial_pwm_derecho.append(pwm_derecho)
        if len(self.historial_pwm_derecho) > 80:
            self.historial_pwm_derecho.pop(0)
        
        self.historial_pwm_izquierdo.append(pwm_izquierdo)
        if len(self.historial_pwm_izquierdo) > 80:
            self.historial_pwm_izquierdo.pop(0)

        if len(self.historial_pwm_izquierdo) > 1:
            step = draw_w / len(self.historial_pwm_izquierdo)
            points_izq = []
            for i, pwm_val in enumerate(self.historial_pwm_izquierdo):
                x = margen_izquierdo + i * step
                pwm_norm = max(pwm_min, min(pwm_max, pwm_val))
                y = margen_superior + (1 - (pwm_norm - pwm_min) / (pwm_max - pwm_min)) * draw_h
                points_izq.append((x, y))
            
            for i in range(len(points_izq) - 1):
                self.salida_canvas.create_line(points_izq[i][0], points_izq[i][1], 
                                              points_izq[i+1][0], points_izq[i+1][1],
                                              fill="#ffaa44", width=2)

        if len(self.historial_pwm_derecho) > 1:
            step = draw_w / len(self.historial_pwm_derecho)
            points_der = []
            for i, pwm_val in enumerate(self.historial_pwm_derecho):
                x = margen_izquierdo + i * step
                pwm_norm = max(pwm_min, min(pwm_max, pwm_val))
                y = margen_superior + (1 - (pwm_norm - pwm_min) / (pwm_max - pwm_min)) * draw_h
                points_der.append((x, y))
            
            for i in range(len(points_der) - 1):
                self.salida_canvas.create_line(points_der[i][0], points_der[i][1], 
                                              points_der[i+1][0], points_der[i+1][1],
                                              fill="#00b4d8", width=2)

        if len(self.historial_pwm_derecho) > 0 and len(self.historial_pwm_izquierdo) > 0:
            pwm_der = self.historial_pwm_derecho[-1]
            pwm_izq = self.historial_pwm_izquierdo[-1]
            
            if self.pwm_vertical == self.PWM_DETENIDO:
                direccion = "⏹ DETENIDO"
                color = "#ff6b6b"
            elif pwm_base > self.PWM_NEUTRO + 5:
                direccion = "⬆ EMERGER"
                color = "#00ff88"
            elif pwm_base < self.PWM_NEUTRO - 5:
                direccion = "⬇ SUMERGIR"
                color = "#ff6b6b"
            else:
                direccion = "✓ NEUTRO"
                color = "#ffaa44"
            
            self.salida_canvas.create_text(w - 5, h - 5, 
                                         text=f"I:{pwm_izq} D:{pwm_der} {direccion}",
                                         fill=color, font=("Arial", 8, "bold"), anchor="se")
        else:
            self.salida_canvas.create_text(w - 5, h - 5, text="--- µs",
                                         fill="#666666", font=("Arial", 8, "bold"), anchor="se")

    def actualizar_interfaz(self):
        try:
            if hasattr(self, 'pwm_vertical_bar'):
                pwm_normalizado = (self.pwm_vertical - self.PWM_MIN) / (self.PWM_MAX - self.PWM_MIN)
                bar_width = pwm_normalizado * 200
                self.pwm_vertical_bar.delete("bar")
                self.pwm_vertical_bar.create_rectangle(0, 0, bar_width, 22, fill="#ff6b6b" if self.pwm_vertical == self.PWM_DETENIDO else self.accent_color, tags="bar")
                
                if self.pwm_vertical == self.PWM_DETENIDO:
                    self.pwm_vertical_bar.itemconfig("bar", fill="#ff6b6b")
                    self.pwm_vertical_label.config(text=f"⏹ DETENIDO ({self.pwm_vertical} µs)", fg="#ff6b6b")
                    self.vertical_label.config(text="⏹ DETENIDO", fg="#ff6b6b")
                elif self.pwm_vertical > self.PWM_NEUTRO + 5:
                    self.pwm_vertical_bar.itemconfig("bar", fill="#ff6b6b")
                    self.pwm_vertical_label.config(text=f"⬇ {self.pwm_vertical} µs", fg="#ff6b6b")
                elif self.pwm_vertical < self.PWM_NEUTRO - 5:
                    self.pwm_vertical_bar.itemconfig("bar", fill="#00ff88")
                    self.pwm_vertical_label.config(text=f"⬆ {self.pwm_vertical} µs", fg="#00ff88")
                else:
                    self.pwm_vertical_bar.itemconfig("bar", fill="#ffaa44")
                    self.pwm_vertical_label.config(text=f"🎯 {self.pwm_vertical} µs", fg="#ffaa44")

            self.dibujar_sonar()
            self.dibujar_error()
            self.dibujar_salida_pid()
            self.mostrar_camara()
            self.actualizar_boton_luz()
            self.dibujar_barra_profundidad()
            self.dibujar_marcas_profundidad()

        except Exception as e:
            print(f"[UI] Error: {e}")
        
        self.root.after(50, self.actualizar_interfaz)

    def actualizar_boton_luz(self):
        if hasattr(self, 'luz_btn'):
            if self.luz_encendida:
                self.luz_btn.config(bg="#ffaa00", relief=tk.SUNKEN)
                self.luz_led.itemconfig(1, fill="#ffaa00")
                self.luz_led.itemconfig(2, fill="#ffdd44")
            else:
                self.luz_btn.config(bg="#444444", relief=tk.RAISED)
                self.luz_led.itemconfig(1, fill="#444444")
                self.luz_led.itemconfig(2, fill="#222222")

    def abrir_ventana_pid(self):
        try:
            if self.pid_window is None:
                self.pid_window = PIDWindow(self)
            elif not self.pid_window.winfo_exists():
                self.pid_window = PIDWindow(self)
            else:
                self.pid_window.lift()
                self.pid_window.focus_force()
        except Exception as e:
            print(f"[PID] Error abriendo ventana: {e}")
            self.pid_window = PIDWindow(self)

    def abrir_ventana_pi(self):
        try:
            if self.pi_window is None:
                self.pi_window = PIWindow(self)
            elif not self.pi_window.winfo_exists():
                self.pi_window = PIWindow(self)
            else:
                self.pi_window.lift()
                self.pi_window.focus_force()
        except Exception as e:
            print(f"[PI] Error abriendo ventana: {e}")
            self.pi_window = PIWindow(self)


# ============================================
# MAIN
# ============================================
def main():
    root = tk.Tk()
    app = ROVInterface(root)
    root.mainloop()


if __name__ == "__main__":
    main()
