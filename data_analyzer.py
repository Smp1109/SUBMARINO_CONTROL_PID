#!/usr/bin/env python3
# ============================================
# PROGRAMA DE ANÁLISIS DE DATOS - PROCESO INDEPENDIENTE
# ============================================
# Este programa se ejecuta como un proceso separado
# Recibe datos del programa principal a través de un socket
# ============================================

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import queue
import json
import socket
import numpy as np
import os
import sys
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ============================================
# SERVIDOR DE DATOS
# ============================================
class DataServer:
    def __init__(self, host='127.0.0.1', port=9999):
        self.host = host
        self.port = port
        self.sock = None
        self.running = True
        self.datos_recibidos = []
        self.cola_datos = queue.Queue()
        self.ultimo_dato = None
        
    def start(self):
        """Inicia el servidor en un hilo"""
        threading.Thread(target=self._servir, daemon=True).start()
        print(f"[SERVER] ✅ Servidor de datos iniciado en {self.host}:{self.port}")
    
    def _servir(self):
        """Bucle principal del servidor"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((self.host, self.port))
            self.sock.listen(5)
            self.sock.settimeout(1.0)
            
            while self.running:
                try:
                    cliente, addr = self.sock.accept()
                    cliente.settimeout(2.0)
                    threading.Thread(target=self._manejar_cliente, args=(cliente,), daemon=True).start()
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"[SERVER] Error: {e}")
                    break
        except Exception as e:
            print(f"[SERVER] ❌ Error iniciando: {e}")
    
    def _manejar_cliente(self, cliente):
        """Maneja la conexión con un cliente"""
        try:
            buffer = ""
            while self.running:
                data = cliente.recv(8192)
                if not data:
                    break
                buffer += data.decode('utf-8', errors='ignore')
                
                while '\n' in buffer:
                    linea, buffer = buffer.split('\n', 1)
                    linea = linea.strip()
                    if not linea:
                        continue
                    try:
                        dato = json.loads(linea)
                        self.cola_datos.put(dato)
                        self.ultimo_dato = dato
                        self.datos_recibidos.append(dato)
                        if len(self.datos_recibidos) > 10000:
                            self.datos_recibidos = self.datos_recibidos[-5000:]
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            print(f"[SERVER] Cliente desconectado: {e}")
        finally:
            try:
                cliente.close()
            except:
                pass
    
    def get_datos(self):
        return self.datos_recibidos.copy()
    
    def get_ultimo_dato(self):
        return self.ultimo_dato
    
    def stop(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass


# ============================================
# VENTANA DE ANÁLISIS DE DATOS CON SCROLL
# ============================================
class DataAnalyzerWindow:
    def __init__(self, root, server):
        self.root = root
        self.server = server
        self.running = True
        
        # ==========================================
        # CONTROL DE RECOLECCIÓN DE DATOS
        # ==========================================
        self.recogiendo_datos = True   # True = recogiendo, False = pausado
        self.datos_pausados = False
        self.muestras_pausa = 0
        
        # ==========================================
        # DATOS ALMACENADOS
        # ==========================================
        self.datos_historial = {
            'tiempo': [],
            'deseada': [],
            'medida': [],
            'error': [],
            'salida_pid': [],
            'pwm': [],
            'pwm_derecho': [],
            'pwm_izquierdo': [],
            'angulo': []
        }
        
        self.datos_auto = {
            'tiempo': [],
            'deseada': [],
            'medida': [],
            'error': [],
            'salida_pid': [],
            'pwm': [],
            'pwm_derecho': [],
            'pwm_izquierdo': [],
            'angulo': []
        }
        
        self.auto_activo = False
        self.tiempo_inicio_auto = 0
        self.limite_datos = None  # 🔴 SIN LÍMITE - GUARDA TODOS LOS DATOS
        self.pausado = False
        self.primer_dato = True
        
        self.pwm_neutro = 1574
        self.altura_deseada = 1.2
        
        # ==========================================
        # CONFIGURACIÓN DE GUI CON SCROLL
        # ==========================================
        self.root.title("📊 ANÁLISIS DE DATOS - PROCESO INDEPENDIENTE")
        self.root.geometry("1400x900")
        self.root.configure(bg="#0a0a1a")
        
        # ==========================================
        # CANVAS CON SCROLLBAR PARA TODA LA VENTANA
        # ==========================================
        main_container = tk.Frame(self.root, bg="#0a0a1a")
        main_container.pack(fill=tk.BOTH, expand=True)
        
        self.canvas_scroll = tk.Canvas(main_container, bg="#0a0a1a", highlightthickness=0)
        scrollbar = tk.Scrollbar(main_container, orient="vertical", command=self.canvas_scroll.yview)
        self.canvas_scroll.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas_scroll.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.scrollable_frame = tk.Frame(self.canvas_scroll, bg="#0a0a1a")
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas_scroll.configure(scrollregion=self.canvas_scroll.bbox("all"))
        )
        
        self.canvas_scroll.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        self._bind_mouse_scroll()
        
        # ==========================================
        # CONTENIDO DENTRO DEL SCROLLABLE FRAME
        # ==========================================
        self.setup_ui()
        
        self.after_id = None
        self.actualizar_datos()
        
        self.hilo_procesamiento = threading.Thread(target=self.procesar_datos, daemon=True)
        self.hilo_procesamiento.start()
        
        self.root.protocol("WM_DELETE_WINDOW", self.cerrar)
    
    def _bind_mouse_scroll(self):
        """Configura el scroll con la rueda del mouse"""
        def on_mousewheel(event):
            self.canvas_scroll.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def on_mousewheel_linux(event):
            if event.num == 4:
                self.canvas_scroll.yview_scroll(-1, "units")
            elif event.num == 5:
                self.canvas_scroll.yview_scroll(1, "units")
        
        self.canvas_scroll.bind_all("<MouseWheel>", on_mousewheel)
        self.canvas_scroll.bind_all("<Button-4>", on_mousewheel_linux)
        self.canvas_scroll.bind_all("<Button-5>", on_mousewheel_linux)
        self.canvas_scroll.bind("<Enter>", lambda e: self.canvas_scroll.focus_set())
    
    def setup_ui(self):
        """Configura la interfaz dentro del scrollable frame"""
        main_frame = tk.Frame(self.scrollable_frame, bg="#0a0a1a")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # ==========================================
        # TÍTULO Y CONTROLES
        # ==========================================
        titulo_frame = tk.Frame(main_frame, bg="#0a0a1a")
        titulo_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(titulo_frame, text="📊 ANÁLISIS DE DATOS - PROCESO INDEPENDIENTE", 
                font=("Arial", 16, "bold"), bg="#0a0a1a", fg="#00b4d8").pack(side=tk.LEFT)
        
        self.conn_label = tk.Label(titulo_frame, text="● CONECTADO", 
                                  font=("Arial", 10, "bold"), bg="#0a0a1a", fg="#00ff88")
        self.conn_label.pack(side=tk.LEFT, padx=20)
        
        btn_frame = tk.Frame(titulo_frame, bg="#0a0a1a")
        btn_frame.pack(side=tk.RIGHT)
        
        self.btn_recoger = tk.Button(btn_frame, text="⏹ DETENER RECOLECCIÓN", 
                                     command=self.toggle_recogida,
                                     bg="#ff6b6b", fg="white", font=("Arial", 10, "bold"),
                                     relief=tk.RAISED, bd=2, padx=12, pady=5)
        self.btn_recoger.pack(side=tk.LEFT, padx=5)
        
        self.btn_pausa = tk.Button(btn_frame, text="⏸ PAUSA VISUAL", command=self.toggle_pausa,
                                  bg="#1f2429", fg="#ffaa44", font=("Arial", 10, "bold"),
                                  relief=tk.RAISED, bd=2, padx=12, pady=5)
        self.btn_pausa.pack(side=tk.LEFT, padx=5)
        
        self.btn_limpiar = tk.Button(btn_frame, text="🔄 LIMPIAR", command=self.limpiar_datos,
                                    bg="#1f2429", fg="#ff6b6b", font=("Arial", 10, "bold"),
                                    relief=tk.RAISED, bd=2, padx=15, pady=5)
        self.btn_limpiar.pack(side=tk.LEFT, padx=5)
        
        # ==========================================
        # SELECCIÓN DE MODO DE GUARDADO
        # ==========================================
        guardado_frame = tk.Frame(titulo_frame, bg="#0a0a1a")
        guardado_frame.pack(side=tk.RIGHT, padx=10)
        
        tk.Label(guardado_frame, text="Guardar:", font=("Arial", 10, "bold"), 
                bg="#0a0a1a", fg="#888888").pack(side=tk.LEFT, padx=5)
        
        self.modo_guardado = tk.StringVar(value="auto")
        
        self.radio_completo = tk.Radiobutton(guardado_frame, text="Completo", 
                                            variable=self.modo_guardado, value="completo",
                                            bg="#0a0a1a", fg="#00b4d8", selectcolor="#0a0a1a",
                                            font=("Arial", 9))
        self.radio_completo.pack(side=tk.LEFT, padx=5)
        
        self.radio_auto = tk.Radiobutton(guardado_frame, text="Solo Auto", 
                                        variable=self.modo_guardado, value="auto",
                                        bg="#0a0a1a", fg="#ffaa44", selectcolor="#0a0a1a",
                                        font=("Arial", 9))
        self.radio_auto.pack(side=tk.LEFT, padx=5)
        self.radio_auto.select()
        
        self.btn_csv = tk.Button(btn_frame, text="📊 CSV", command=self.exportar_csv,
                                bg="#1f2429", fg="#00b4d8", font=("Arial", 10, "bold"),
                                relief=tk.RAISED, bd=2, padx=15, pady=5)
        self.btn_csv.pack(side=tk.LEFT, padx=5)
        
        self.btn_mat = tk.Button(btn_frame, text="🔬 MAT", command=self.exportar_mat,
                                bg="#1f2429", fg="#ff6b6b", font=("Arial", 10, "bold"),
                                relief=tk.RAISED, bd=2, padx=15, pady=5)
        self.btn_mat.pack(side=tk.LEFT, padx=5)
        
        # ==========================================
        # INFORMACIÓN DE ESTADO
        # ==========================================
        info_frame = tk.Frame(main_frame, bg="#0d1117", highlightbackground="#1f2429", highlightthickness=1)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.lbl_estado = tk.Label(info_frame, 
                                  text="Estado: 🟢 RECIBIENDO | Muestras: 0 | Auto: 0 | Modo: INACTIVO",
                                  font=("Arial", 10), bg="#0d1117", fg="#888888")
        self.lbl_estado.pack(side=tk.LEFT, padx=10, pady=5)
        
        self.lbl_auto = tk.Label(info_frame, text="⏹ AUTO: INACTIVO", 
                                font=("Arial", 10, "bold"), bg="#0d1117", fg="#666666")
        self.lbl_auto.pack(side=tk.RIGHT, padx=10, pady=5)
        
        # ==========================================
        # GRÁFICAS CON MATPLOTLIB
        # ==========================================
        graficas_frame = tk.Frame(main_frame, bg="#0a0a1a")
        graficas_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.fig = Figure(figsize=(13, 7), facecolor='#0a0a1a')
        self.fig.subplots_adjust(left=0.06, right=0.78, bottom=0.08, top=0.92, hspace=0.4, wspace=0.3)
        
        # Gráfica 1: Profundidad
        self.ax1 = self.fig.add_subplot(2, 2, 1)
        self.ax1.set_facecolor('#0d1117')
        self.ax1.set_xlabel('Tiempo (s)', color='#888888')
        self.ax1.set_ylabel('Profundidad (m)', color='#888888')
        self.ax1.tick_params(colors='#888888')
        self.ax1.grid(True, alpha=0.2, color='#444444')
        self.line_deseada, = self.ax1.plot([], [], 'g-', linewidth=2, label='Deseada')
        self.line_medida, = self.ax1.plot([], [], 'b-', linewidth=2, label='Medida')
        self.ax1.legend(loc='upper right', facecolor='#0d1117', labelcolor='#e0e0e0')
        
        # Gráfica 2: Error
        self.ax2 = self.fig.add_subplot(2, 2, 2)
        self.ax2.set_facecolor('#0d1117')
        self.ax2.set_xlabel('Tiempo (s)', color='#888888')
        self.ax2.set_ylabel('Error (m)', color='#888888')
        self.ax2.tick_params(colors='#888888')
        self.ax2.grid(True, alpha=0.2, color='#444444')
        self.line_error, = self.ax2.plot([], [], 'r-', linewidth=2)
        self.ax2.axhline(y=0, color='#444444', linestyle='--')
        
        # Gráfica 3: Salida PID
        self.ax3 = self.fig.add_subplot(2, 2, 3)
        self.ax3.set_facecolor('#0d1117')
        self.ax3.set_xlabel('Tiempo (s)', color='#888888')
        self.ax3.set_ylabel('Salida PID', color='#888888')
        self.ax3.tick_params(colors='#888888')
        self.ax3.grid(True, alpha=0.2, color='#444444')
        self.line_salida, = self.ax3.plot([], [], 'm-', linewidth=2)
        self.ax3.axhline(y=0, color='#444444', linestyle='--')
        self.ax3.set_ylim(-1.2, 1.2)
        
        # Gráfica 4: PWM
        self.ax4 = self.fig.add_subplot(2, 2, 4)
        self.ax4.set_facecolor('#0d1117')
        self.ax4.set_xlabel('Tiempo (s)', color='#888888')
        self.ax4.set_ylabel('PWM (µs)', color='#888888')
        self.ax4.tick_params(colors='#888888')
        self.ax4.grid(True, alpha=0.2, color='#444444')
        self.ax4.set_ylim(1100, 1900)
        
        self.line_pwm_der, = self.ax4.plot([], [], '#00b4d8', linewidth=2.5, label='Motor DERECHO')
        self.line_pwm_izq, = self.ax4.plot([], [], '#ffaa44', linewidth=2.5, label='Motor IZQUIERDO')
        
        self.ax4.axhline(y=1500, color='#ff6b6b', linestyle='--', alpha=0.5, linewidth=1, label='Detenido (1500µs)')
        self.ax4.axhline(y=self.pwm_neutro, color='#888888', linestyle=':', alpha=0.7, linewidth=1, label=f'Neutro ({self.pwm_neutro}µs)')
        
        self.ax4.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), 
                       facecolor='#0d1117', labelcolor='#e0e0e0',
                       framealpha=0.95, edgecolor='#1f2429',
                       fontsize=10, borderpad=1.5)
        
        self.canvas = FigureCanvasTkAgg(self.fig, graficas_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # ==========================================
        # 🔴 TABLA DE DATOS - CORREGIDA
        # ==========================================
        tabla_frame = tk.LabelFrame(main_frame, text="📋 DATOS EN TIEMPO REAL", 
                                   font=("Arial", 10, "bold"), bg="#0d1117",
                                   fg="#ffffff", relief=tk.RIDGE, bd=2)
        # 🔴 expand=True para que ocupe espacio y sea visible
        tabla_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 5), ipadx=5, ipady=5)
        
        tabla_container = tk.Frame(tabla_frame, bg="#0d1117")
        tabla_container.pack(fill=tk.BOTH, expand=True)
        
        vsb = ttk.Scrollbar(tabla_container, orient="vertical")
        hsb = ttk.Scrollbar(tabla_container, orient="horizontal")
        
        self.tabla = ttk.Treeview(tabla_container, 
                                 columns=("Tiempo", "Deseada", "Medida", "Error", "Salida PID", "PWM", "PWM Der", "PWM Izq"),
                                 show="headings",
                                 height=8,
                                 yscrollcommand=vsb.set,
                                 xscrollcommand=hsb.set)
        
        vsb.config(command=self.tabla.yview)
        hsb.config(command=self.tabla.xview)
        
        columnas = [
            ("Tiempo", "Tiempo (s)", 100),
            ("Deseada", "Deseada (m)", 120),
            ("Medida", "Medida (m)", 120),
            ("Error", "Error (m)", 110),
            ("Salida PID", "Salida PID", 110),
            ("PWM", "PWM (µs)", 110),
            ("PWM Der", "PWM Der (µs)", 110),
            ("PWM Izq", "PWM Izq (µs)", 110)
        ]
        
        for col, header, width in columnas:
            self.tabla.heading(col, text=header)
            self.tabla.column(col, width=width, anchor="center")
        
        self.tabla.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", 
                       background="#0a0a1a",
                       foreground="#e0e0e0",
                       fieldbackground="#0a0a1a",
                       font=("Arial", 9))
        style.configure("Treeview.Heading",
                       background="#1a1a2e",
                       foreground="#00b4d8",
                       font=("Arial", 9, "bold"))
        style.map("Treeview", 
                 background=[('selected', '#1a3a5c')],
                 foreground=[('selected', '#ffffff')])
        
        # ==========================================
        # INFORMACIÓN DE MUESTRAS
        # ==========================================
        info_muestras_frame = tk.Frame(main_frame, bg="#0a0a1a")
        info_muestras_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.lbl_muestras = tk.Label(info_muestras_frame, 
                                    text="Muestras en tabla: 0 | Total recibidas: 0 | Auto: 0",
                                    font=("Arial", 9), bg="#0a0a1a", fg="#666666")
        self.lbl_muestras.pack(side=tk.LEFT, padx=5)
        
        self.lbl_ultimo_dato = tk.Label(info_muestras_frame,
                                       text="Último dato: ---",
                                       font=("Arial", 9), bg="#0a0a1a", fg="#666666")
        self.lbl_ultimo_dato.pack(side=tk.RIGHT, padx=5)
        
        # ==========================================
        # NOTA SOBRE EL SCROLL
        # ==========================================
        nota_frame = tk.Frame(main_frame, bg="#0a0a1a")
        nota_frame.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(nota_frame, text="💡 Usa la rueda del mouse para hacer scroll en la ventana",
                font=("Arial", 9), bg="#0a0a1a", fg="#555555").pack()
    
    def procesar_datos(self):
        """Hilo que procesa los datos del servidor"""
        while self.running:
            try:
                dato = self.server.cola_datos.get(timeout=0.1)
                if dato is None:
                    continue
                self._procesar_dato(dato)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[PROCESADOR] Error: {e}")
    
    def _procesar_dato(self, dato):
        """Procesa un dato recibido - SIN LÍMITE"""
        try:
            if not self.recogiendo_datos:
                self.ultimo_dato_recibido = dato
                return
            
            tiempo = dato.get('tiempo', 0)
            deseada = dato.get('deseada', 0)
            medida = dato.get('medida', 0)
            error = dato.get('error', 0)
            salida_pid = dato.get('salida_pid', 0)
            pwm = dato.get('pwm', 0)
            pwm_derecho = dato.get('pwm_derecho', 0)
            pwm_izquierdo = dato.get('pwm_izquierdo', 0)
            angulo = dato.get('angulo', 0)
            modo_auto = dato.get('modo_auto', False)
            
            if 'pwm_neutro' in dato:
                self.pwm_neutro = dato['pwm_neutro']
            if 'altura_deseada' in dato:
                self.altura_deseada = dato['altura_deseada']
            
            if modo_auto and not self.auto_activo:
                self.auto_activo = True
                self.tiempo_inicio_auto = time.time()
                for key in self.datos_auto:
                    self.datos_auto[key] = []
                print(f"[ANALYZER] 🔴 AUTO INICIADO")
                
            elif not modo_auto and self.auto_activo:
                self.auto_activo = False
                print(f"[ANALYZER] ⏹ AUTO FINALIZADO - Muestras: {len(self.datos_auto['tiempo'])}")
            
            # Guardar en historial (SIN LÍMITE)
            self.datos_historial['tiempo'].append(tiempo)
            self.datos_historial['deseada'].append(deseada)
            self.datos_historial['medida'].append(medida)
            self.datos_historial['error'].append(error)
            self.datos_historial['salida_pid'].append(salida_pid)
            self.datos_historial['pwm'].append(pwm)
            self.datos_historial['pwm_derecho'].append(pwm_derecho)
            self.datos_historial['pwm_izquierdo'].append(pwm_izquierdo)
            self.datos_historial['angulo'].append(angulo)
            
            # ✅ CORREGIDO: SOLO recortar SI hay límite definido
            if self.limite_datos is not None:
                for key in self.datos_historial:
                    if len(self.datos_historial[key]) > self.limite_datos:
                        self.datos_historial[key] = self.datos_historial[key][-self.limite_datos:]
            
            if self.auto_activo and modo_auto and self.recogiendo_datos:
                tiempo_auto = time.time() - self.tiempo_inicio_auto
                self.datos_auto['tiempo'].append(tiempo_auto)
                self.datos_auto['deseada'].append(deseada)
                self.datos_auto['medida'].append(medida)
                self.datos_auto['error'].append(error)
                self.datos_auto['salida_pid'].append(salida_pid)
                self.datos_auto['pwm'].append(pwm)
                self.datos_auto['pwm_derecho'].append(pwm_derecho)
                self.datos_auto['pwm_izquierdo'].append(pwm_izquierdo)
                self.datos_auto['angulo'].append(angulo)
                
                # ✅ CORREGIDO: TAMBIÉN para datos_auto
                if self.limite_datos is not None:
                    for key in self.datos_auto:
                        if len(self.datos_auto[key]) > self.limite_datos:
                            self.datos_auto[key] = self.datos_auto[key][-self.limite_datos:]
            
            self.root.after(0, self._actualizar_ui, tiempo, deseada, medida, error, 
                           salida_pid, pwm, pwm_derecho, pwm_izquierdo, modo_auto)
            
        except Exception as e:
            print(f"[PROCESADOR] Error procesando dato: {e}")
    
    def _actualizar_ui(self, tiempo, deseada, medida, error, salida_pid, pwm, pwm_derecho, pwm_izquierdo, modo_auto):
        """Actualiza la interfaz en el hilo principal - TABLA SIEMPRE VISIBLE"""
        try:
            # ==========================================
            # ACTUALIZAR TABLA - SIEMPRE (incluso en pausa)
            # ==========================================
            valores = (
                f"{tiempo:.2f}",
                f"{deseada:.2f}",
                f"{medida:.2f}",
                f"{error:+.2f}",
                f"{salida_pid:+.2f}",
                f"{pwm:.0f}",
                f"{pwm_derecho:.0f}",
                f"{pwm_izquierdo:.0f}"
            )
            
            self.tabla.insert("", tk.END, values=valores)
            
            hijos = self.tabla.get_children()
            if len(hijos) > 100:
                for hijo in hijos[:-100]:
                    self.tabla.delete(hijo)
            
            if len(hijos) > 0:
                self.tabla.see(hijos[-1])
            
            # ==========================================
            # ACTUALIZAR ESTADO
            # ==========================================
            if self.auto_activo:
                self.lbl_auto.config(text="🔴 AUTO: ACTIVO", fg="#ff6b6b")
            else:
                self.lbl_auto.config(text="⏹ AUTO: INACTIVO", fg="#666666")
            
            estado_texto = f"Estado: {'🔴 PAUSADO' if not self.recogiendo_datos else '🟢 RECIBIENDO'} | "
            estado_texto += f"Muestras: {len(self.datos_historial['tiempo'])} | "
            estado_texto += f"Auto: {len(self.datos_auto['tiempo'])} | "
            estado_texto += f"Modo: {'ACTIVO' if self.auto_activo else 'INACTIVO'}"
            
            self.lbl_estado.config(text=estado_texto)
            
            # ==========================================
            # ACTUALIZAR INFO DE MUESTRAS
            # ==========================================
            self.lbl_muestras.config(
                text=f"Muestras en tabla: {len(self.tabla.get_children())} | "
                     f"Total: {len(self.datos_historial['tiempo'])} | "
                     f"Auto: {len(self.datos_auto['tiempo'])}"
            )
            
            self.lbl_ultimo_dato.config(
                text=f"Último dato: t={tiempo:.1f}s | PWM={pwm:.0f}µs | Error={error:+.2f}m"
            )
            
            # ==========================================
            # ACTUALIZAR GRÁFICAS
            # ==========================================
            self._actualizar_graficas()
            
        except Exception as e:
            print(f"[UI] Error actualizando: {e}")
    
    def _actualizar_graficas(self):
        """Actualiza las gráficas con TODOS los datos"""
        if not self.datos_historial['tiempo'] or len(self.datos_historial['tiempo']) < 2:
            return
        
        try:
            t = self.datos_historial['tiempo']
            
            self.line_deseada.set_data(t, self.datos_historial['deseada'])
            self.line_medida.set_data(t, self.datos_historial['medida'])
            self.ax1.relim()
            self.ax1.autoscale_view()
            
            self.line_error.set_data(t, self.datos_historial['error'])
            self.ax2.relim()
            self.ax2.autoscale_view()
            
            self.line_salida.set_data(t, self.datos_historial['salida_pid'])
            self.ax3.relim()
            self.ax3.autoscale_view()
            self.ax3.set_ylim(-1.2, 1.2)
            
            if self.datos_historial['pwm_derecho'] and self.datos_historial['pwm_izquierdo']:
                self.line_pwm_der.set_data(t, self.datos_historial['pwm_derecho'])
                self.line_pwm_izq.set_data(t, self.datos_historial['pwm_izquierdo'])
            
            self.ax4.relim()
            self.ax4.autoscale_view()
            self.ax4.set_ylim(1100, 1900)
            
            self.canvas.draw_idle()
            
        except Exception as e:
            print(f"[GRAFICAS] Error: {e}")
    
    def actualizar_datos(self):
        """Actualización periódica de la interfaz"""
        if not self.pausado:
            try:
                if self.server.ultimo_dato is not None:
                    self.conn_label.config(text="● CONECTADO", fg="#00ff88")
                else:
                    self.conn_label.config(text="○ SIN DATOS", fg="#ffaa44")
            except:
                pass
        
        self.after_id = self.root.after(200, self.actualizar_datos)
    
    # ==========================================
    # CONTROLES
    # ==========================================
    
    def toggle_recogida(self):
        """Alterna entre recoger datos y pausar la recolección"""
        self.recogiendo_datos = not self.recogiendo_datos
        
        if self.recogiendo_datos:
            self.btn_recoger.config(text="⏹ DETENER RECOLECCIÓN", bg="#ff6b6b", fg="white")
            print("[RECORDER] ▶️ RECOLECCIÓN REANUDADA")
            self.datos_pausados = False
        else:
            self.btn_recoger.config(text="▶️ CONTINUAR RECOLECCIÓN", bg="#00b4d8", fg="white")
            print("[RECORDER] ⏹ RECOLECCIÓN DETENIDA")
            self.datos_pausados = True
    
    def toggle_pausa(self):
        self.pausado = not self.pausado
        self.btn_pausa.config(text="▶ REANUDAR" if self.pausado else "⏸ PAUSA VISUAL")
    
    def limpiar_datos(self):
        if messagebox.askyesno("Limpiar", "¿Limpiar todos los datos?"):
            for key in self.datos_historial:
                self.datos_historial[key] = []
            for key in self.datos_auto:
                self.datos_auto[key] = []
            self.tabla.delete(*self.tabla.get_children())
            self.auto_activo = False
            self.primer_dato = True
            self.lbl_muestras.config(text="Muestras en tabla: 0 | Total recibidas: 0 | Auto: 0")
            self.lbl_ultimo_dato.config(text="Último dato: ---")
            print("[ANALYZER] Datos limpiados")
    
    # ==========================================
    # EXPORTACIÓN DE DATOS
    # ==========================================
    
    def get_datos_completos(self):
        if len(self.datos_historial['tiempo']) < 1:
            return None
        return {k: v.copy() for k, v in self.datos_historial.items()}
    
    def get_datos_auto(self):
        if len(self.datos_auto['tiempo']) < 1:
            return None
        return {k: v.copy() for k, v in self.datos_auto.items()}
    
    def exportar_csv(self):
        """Exporta datos a CSV con diálogo robusto"""
        from tkinter import filedialog
        import os
        
        modo = self.modo_guardado.get()
        
        if modo == "auto":
            datos = self.get_datos_auto()
            titulo = "MODO AUTOMÁTICO"
            muestras = len(self.datos_auto['tiempo'])
        else:
            datos = self.get_datos_completos()
            titulo = "COMPLETO (Histórico)"
            muestras = len(self.datos_historial['tiempo'])
        
        if datos is None:
            messagebox.showerror("Error", 
                f"No hay datos de {titulo} para exportar.\n"
                f"Muestras disponibles: {muestras}")
            return
        
        self.root.lift()
        self.root.focus_force()
        self.root.attributes('-topmost', True)
        self.root.update()
        time.sleep(0.05)
        
        archivo = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title=f"Guardar datos {titulo} ({muestras} muestras)",
            parent=self.root,
            initialdir=os.path.expanduser("~"),
            initialfile=f"datos_rov_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        self.root.attributes('-topmost', False)
        
        if archivo:
            try:
                self._guardar_csv(archivo, datos, titulo)
                messagebox.showinfo("Éxito", f"✅ Datos exportados a:\n{archivo}")
                print(f"[EXPORT] CSV guardado: {archivo}")
            except Exception as e:
                messagebox.showerror("Error", f"Error al guardar:\n{str(e)}")
        else:
            print("[EXPORT] Usuario canceló el guardado")
    
    def _guardar_csv(self, archivo, datos, titulo):
        try:
            sep = ";"
            
            with open(archivo, 'w', encoding='utf-8-sig') as f:
                f.write(f"# DATOS DEL ROV - {titulo}\n")
                f.write(f"# Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Muestras: {len(datos['tiempo'])}\n")
                f.write(f"# PWM Neutro: {self.pwm_neutro} µs\n")
                f.write(f"# Altura deseada: {self.altura_deseada:.2f} m\n")
                f.write("# ========================================\n\n")
                
                f.write(f"Tiempo(s){sep}Deseada(m){sep}Medida(m){sep}Error(m){sep}Salida_PID{sep}PWM(us){sep}PWM_Der(us){sep}PWM_Izq(us){sep}Angulo(°)\n")
                
                for i in range(len(datos['tiempo'])):
                    f.write(f"{datos['tiempo'][i]:.3f}{sep}"
                           f"{datos['deseada'][i]:.3f}{sep}"
                           f"{datos['medida'][i]:.3f}{sep}"
                           f"{datos['error'][i]:+.3f}{sep}"
                           f"{datos['salida_pid'][i]:.3f}{sep}"
                           f"{datos['pwm'][i]:.0f}{sep}"
                           f"{datos.get('pwm_derecho', [0])[i]:.0f}{sep}"
                           f"{datos.get('pwm_izquierdo', [0])[i]:.0f}{sep}"
                           f"{datos.get('angulo', [0])[i]:.1f}\n")
            
            print(f"[EXPORT] CSV guardado: {archivo}")
        except Exception as e:
            raise Exception(f"Error guardando CSV: {str(e)}")
    
    def exportar_mat(self):
        """Exporta datos a MATLAB .mat con diálogo robusto"""
        try:
            import scipy.io as sio
        except ImportError:
            messagebox.showerror("Error", "Se requiere scipy. Instala: pip install scipy")
            return
        
        import os
        
        modo = self.modo_guardado.get()
        
        if modo == "auto":
            datos = self.get_datos_auto()
            titulo = "MODO AUTOMÁTICO"
            muestras = len(self.datos_auto['tiempo'])
        else:
            datos = self.get_datos_completos()
            titulo = "COMPLETO (Histórico)"
            muestras = len(self.datos_historial['tiempo'])
        
        if datos is None:
            messagebox.showerror("Error", 
                f"No hay datos de {titulo} para exportar.\n"
                f"Muestras disponibles: {muestras}")
            return
        
        self.root.lift()
        self.root.focus_force()
        self.root.attributes('-topmost', True)
        self.root.update()
        time.sleep(0.05)
        
        archivo = filedialog.asksaveasfilename(
            defaultextension=".mat",
            filetypes=[("MATLAB files", "*.mat"), ("All files", "*.*")],
            title=f"Guardar datos {titulo} para MATLAB ({muestras} muestras)",
            parent=self.root,
            initialdir=os.path.expanduser("~"),
            initialfile=f"datos_rov_{time.strftime('%Y%m%d_%H%M%S')}.mat"
        )
        
        self.root.attributes('-topmost', False)
        
        if archivo:
            try:
                datos_mat = {
                    'tiempo': np.array(datos['tiempo']),
                    'deseada': np.array(datos['deseada']),
                    'medida': np.array(datos['medida']),
                    'error': np.array(datos['error']),
                    'salida_pid': np.array(datos['salida_pid']),
                    'pwm': np.array(datos['pwm']),
                    'pwm_derecho': np.array(datos.get('pwm_derecho', [0] * len(datos['tiempo']))),
                    'pwm_izquierdo': np.array(datos.get('pwm_izquierdo', [0] * len(datos['tiempo']))),
                    'angulo': np.array(datos.get('angulo', [0] * len(datos['tiempo']))),
                    'pwm_neutro': self.pwm_neutro,
                    'altura_deseada': self.altura_deseada,
                    'descripcion': f'Datos del ROV - {titulo}',
                    'fecha_creacion': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                
                sio.savemat(archivo, datos_mat)
                messagebox.showinfo("Éxito", f"✅ Datos exportados a:\n{archivo}")
                print(f"[EXPORT] MAT guardado: {archivo}")
            except Exception as e:
                messagebox.showerror("Error", f"Error al exportar:\n{str(e)}")
        else:
            print("[EXPORT] Usuario canceló el guardado")
    
    def cerrar(self):
        self.running = False
        if self.after_id:
            self.root.after_cancel(self.after_id)
        self.server.stop()
        self.root.destroy()


# ============================================
# FUNCIÓN PARA EJECUTAR DESDE OTRO PROCESO
# ============================================
def ejecutar_analizador():
    """Función que se ejecuta en el proceso separado"""
    server = DataServer(host='127.0.0.1', port=9999)
    server.start()
    
    root = tk.Tk()
    app = DataAnalyzerWindow(root, server)
    root.mainloop()


if __name__ == "__main__":
    ejecutar_analizador()