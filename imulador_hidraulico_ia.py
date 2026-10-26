import pygame
import sys
import math
import random
import time


# CONFIGURACIÓN GENERAL Y PALETA DE COLORES

WIDTH, HEIGHT = 1360, 800
FPS = 60

C_BG_DARK   = (13, 17, 23)
C_PANEL     = (22, 27, 34)
C_BORDER    = (48, 54, 61)
C_TEXT_MAIN = (240, 246, 252)
C_TEXT_MUTED= (139, 148, 158)

C_CYAN      = (56, 189, 248)
C_BLUE_WATER= (37, 99, 235)
C_GREEN_OK  = (34, 197, 94)
C_AMBER_WARN= (245, 158, 11)
C_RED_DANGER= (239, 68, 68)


# MODELO DE AGENTE INTELIGENTE: MOTOR DE INFERENCIA Y REGLAS EXPERTAS (REAS/PAMA)

class WaterInferenceEngine:
    def __init__(self):
        self.rules_fired = []

    def evaluate(self, perceptions):
        flow = perceptions["flow"]
        hour = perceptions["hour"]
        tank_level = perceptions["tank_level"]
        pump_active = perceptions["pump_active"]
        is_away = perceptions["is_away"]
        
        self.rules_fired.clear()
        state = "NORMAL"
        severity = "INFO"
        diagnosis = "Consumo habitual dentro de los rangos esperados."
        action = "Sin acción requerida. Monitoreo continuo activo."
        rule_id = "R-00"

        # R-03: Falla en flotador de tinaco / Riesgo de desborde
        if tank_level >= 99.5 and not pump_active and flow > 1.5:
            rule_id = "R-03"
            state = "RIESGO_DESBORDE"
            severity = "CRITICA"
            diagnosis = "Flujo entrante continuo con tinaco al 100% de capacidad y bomba inactiva."
            action = "Revisar válvula mecánica de flotador o vástago atascado en tinaco."
            self.rules_fired.append(rule_id)

        # R-07: Fuga mayor o ruptura de tubería / llave olvidada
        elif flow >= 25.0:
            rule_id = "R-07"
            state = "FUGA_MAYOR_EMERGENCIA"
            severity = "CRITICA"
            diagnosis = f"Caudal excesivo sostenido ({flow:.1f} L/min). Posible rotura estructural o llave abierta."
            action = "Cerrar inmediatamente la llave de paso principal e inspeccionar red troncal."
            self.rules_fired.append(rule_id)

        # R-02: Fuga silenciosa nocturna o en ausencia
        elif (flow >= 0.4 and (1 <= hour < 5 or is_away)):
            rule_id = "R-02"
            state = "ALERTA_FUGA_SILENCIOSA"
            severity = "ADVERTENCIA"
            diagnosis = f"Caudal continuo anómalo ({flow:.1f} L/min) detectado durante ventana de inactividad humana."
            action = "Revisar sello 'sapito' de inodoros, empaques de regaderas o llaves de jardín."
            self.rules_fired.append(rule_id)

        # R-05: Consumo pico legítimo
        elif flow > 15.0 and (6 <= hour <= 22):
            rule_id = "R-05"
            state = "CONSUMO_ALTO_NORMAL"
            severity = "MODERADA"
            diagnosis = "Pico volumétrico diurno correspondiente a uso intensivo legítimo (baño/lavado)."
            action = "Optimizar tiempos de ducha y ciclos de lavado para evitar brincos tarifarios."
            self.rules_fired.append(rule_id)

        return {
            "rule_id": rule_id,
            "state": state,
            "severity": severity,
            "diagnosis": diagnosis,
            "action": action
        }


# ENTORNO DINÁMICO Y SIMULACIÓN HIDRÁULICA

class HydraulicEnvironment:
    def __init__(self):
        self.flow_history = [0.0] * 80
        self.reset()

    def reset(self):
        self.hour_float = 2.0       # Comienza en la madrugada (02:00 am)
        self.sim_speed = 0.5        # Horas simuladas por segundo
        self.tank_level = 85.0      # Porcentaje
        self.cistern_level = 90.0
        self.pump_active = False
        self.is_away = False
        
        # Apagar anomalías
        self.leak_toilet = False
        self.pipe_burst = False
        self.float_valve_broken = False
        self.total_liters = 0.0
        self.flow_history = [0.0] * 80

    def update(self, dt):
        self.hour_float = (self.hour_float + dt * self.sim_speed) % 24.0
        h = int(self.hour_float)

        # Curva horaria residencial
        if 0 <= h < 5:
            base_flow = 0.0
        elif 6 <= h <= 8:
            base_flow = random.uniform(8.0, 16.0)
        elif 13 <= h <= 15:
            base_flow = random.uniform(4.0, 9.0)
        elif 19 <= h <= 21:
            base_flow = random.uniform(6.0, 12.0)
        else:
            base_flow = random.uniform(0.0, 2.0)

        if self.is_away:
            base_flow = 0.0

        # Anomalías inyectadas
        leak_flow = 0.0
        if self.leak_toilet:
            leak_flow += 0.85
        if self.pipe_burst:
            leak_flow += 30.0
        if self.float_valve_broken:
            self.tank_level = 100.0
            leak_flow += 2.5

        current_flow = base_flow + leak_flow
        
        # Dinámica de tinaco
        if self.float_valve_broken:
            self.tank_level = 100.0
        elif current_flow > 0:
            self.tank_level = max(0.0, self.tank_level - (current_flow * dt * 0.05))

        self.total_liters += current_flow * (dt * 60.0 * self.sim_speed)
        self.flow_history.append(current_flow)
        if len(self.flow_history) > 80:
            self.flow_history.pop(0)

        return {
            "flow": current_flow,
            "hour": h,
            "hour_full": self.hour_float,
            "tank_level": self.tank_level,
            "cistern_level": self.cistern_level,
            "pump_active": self.pump_active,
            "is_away": self.is_away
        }


# APLICACIÓN DE INTERFAZ GRÁFICA (DASHBOARD ANALÍTICO)

class WaterSimulationApp:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("UNACH · Sistema Inteligente de Gestión Hídrica Residencial")
        self.clock = pygame.time.Clock()

        self.f_title = pygame.font.SysFont("segoeui", 18, bold=True)
        self.f_sub   = pygame.font.SysFont("segoeui", 12)
        self.f_bold  = pygame.font.SysFont("segoeui", 13, bold=True)
        self.f_body  = pygame.font.SysFont("segoeui", 12)
        self.f_mono  = pygame.font.SysFont("consolas", 11)
        self.f_big   = pygame.font.SysFont("consolas", 28, bold=True)

        self.env = HydraulicEnvironment()
        self.ai = WaterInferenceEngine()
        
        self.decision_log = []
        self.last_log_state = None

        # Botones de control
        self.btn_leak   = pygame.Rect(40, 440, 340, 34)
        self.btn_float  = pygame.Rect(40, 482, 340, 34)
        self.btn_burst  = pygame.Rect(40, 524, 340, 34)
        self.btn_away   = pygame.Rect(40, 566, 340, 34)
        self.btn_refill = pygame.Rect(40, 608, 340, 34)
        self.btn_reset  = pygame.Rect(40, 650, 340, 34)

    def add_log(self, text, severity):
        h = int(self.env.hour_float)
        m = int((self.env.hour_float % 1) * 60)
        stamp = f"{h:02d}:{m:02d} hrs"
        self.decision_log.insert(0, (stamp, text, severity))
        if len(self.decision_log) > 20:
            self.decision_log.pop()

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0

            perceptions = self.env.update(dt)
            decision = self.ai.evaluate(perceptions)

            if decision["state"] != self.last_log_state and decision["state"] != "NORMAL":
                self.add_log(f"[{decision['rule_id']}] {decision['diagnosis']}", decision["severity"])
                self.last_log_state = decision["state"]
            elif decision["state"] == "NORMAL" and self.last_log_state != "NORMAL":
                self.add_log("Condiciones normalizadas en la red hidráulica.", "INFO")
                self.last_log_state = "NORMAL"


            # GESTIÓN DE EVENTOS DE ENTRADA, TECLADO Y BOTONES

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_r:
                        self.env.reset()
                        self.decision_log.clear()
                        self.last_log_state = None
                        self.add_log("Simulación reiniciada a las 02:00 hrs.", "INFO")

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    if self.btn_leak.collidepoint(mx, my):
                        self.env.leak_toilet = not self.env.leak_toilet
                    elif self.btn_float.collidepoint(mx, my):
                        self.env.float_valve_broken = not self.env.float_valve_broken
                    elif self.btn_burst.collidepoint(mx, my):
                        self.env.pipe_burst = not self.env.pipe_burst
                    elif self.btn_away.collidepoint(mx, my):
                        self.env.is_away = not self.env.is_away
                    elif self.btn_refill.collidepoint(mx, my):
                        self.env.tank_level = 90.0
                    elif self.btn_reset.collidepoint(mx, my):
                        self.env.reset()
                        self.decision_log.clear()
                        self.last_log_state = None
                        self.add_log("Simulación reiniciada a las 02:00 hrs.", "INFO")

            self.render(perceptions, decision)
            pygame.display.flip()

        pygame.quit()
        sys.exit()

    def render(self, perceptions, decision):
        self.screen.fill(C_BG_DARK)

        # Encabezado
        top_rect = pygame.Rect(20, 15, WIDTH - 40, 65)
        pygame.draw.rect(self.screen, C_PANEL, top_rect, border_radius=12)
        pygame.draw.rect(self.screen, C_BORDER, top_rect, 1, border_radius=12)
        
        self.screen.blit(self.f_title.render("UNACH · SISTEMA INTELIGENTE DE GESTIÓN HÍDRICA RESIDENCIAL", True, C_TEXT_MAIN), (38, 25))
        self.screen.blit(self.f_sub.render("Prototipo de Inferencia Basada en Conocimiento y Supervisión Predictiva (Entrega 2) (Hecho por el Equipo 6)", True, C_TEXT_MUTED), (38, 50))

        h = int(perceptions["hour_full"])
        m = int((perceptions["hour_full"] % 1) * 60)
        time_str = f"Reloj: {h:02d}:{m:02d} hrs"
        mode_str = "MODO: FUERA DE CASA" if perceptions["is_away"] else "MODO: HABITADO"
        self.screen.blit(self.f_mono.render(time_str, True, C_CYAN), (WIDTH - 240, 27))
        self.screen.blit(self.f_mono.render(mode_str, True, C_AMBER_WARN if perceptions["is_away"] else C_GREEN_OK), (WIDTH - 240, 48))

        # Columna 1
        p1 = pygame.Rect(20, 95, 380, 685)
        pygame.draw.rect(self.screen, C_PANEL, p1, border_radius=12)
        pygame.draw.rect(self.screen, C_BORDER, p1, 1, border_radius=12)

        self.screen.blit(self.f_bold.render("TELEMETRÍA DE RED HIDRÁULICA", True, C_TEXT_MAIN), (40, 110))

        pygame.draw.rect(self.screen, (30, 41, 59), (130, 140, 160, 100), border_radius=8)
        water_h = int((perceptions["tank_level"] / 100.0) * 96)
        pygame.draw.rect(self.screen, C_BLUE_WATER, (132, 142 + (96 - water_h), 156, water_h), border_radius=6)
        pygame.draw.rect(self.screen, C_BORDER, (130, 140, 160, 100), 2, border_radius=8)
        self.screen.blit(self.f_bold.render("TINACO 1100 L", True, C_TEXT_MAIN), (165, 172))
        self.screen.blit(self.f_mono.render(f"{perceptions['tank_level']:.1f}%", True, C_TEXT_MAIN), (185, 192))

        metrics_y = 260
        metrics = [
            ("Caudal Instantáneo:", f"{perceptions['flow']:.2f} L/min", C_CYAN),
            ("Nivel Almacenamiento:", f"{perceptions['tank_level']:.1f} %", C_TEXT_MAIN),
            ("Volumen Acumulado:", f"{self.env.total_liters:.1f} Litros", C_TEXT_MAIN),
            ("Gasto Proyectado Mes:", f"{(self.env.total_liters * 0.03 * 30):.1f} m³", C_AMBER_WARN),
        ]
        for label, val, col in metrics:
            self.screen.blit(self.f_body.render(label, True, C_TEXT_MUTED), (40, metrics_y))
            self.screen.blit(self.f_bold.render(val, True, col), (220, metrics_y))
            metrics_y += 28

        self.screen.blit(self.f_bold.render("CONTROL Y PRUEBAS EXPERIMENTALES", True, C_TEXT_MAIN), (40, 412))
        
        self._draw_btn(self.btn_leak, "Fuga Silenciosa Inodoro (0.8 L/min)", self.env.leak_toilet)
        self._draw_btn(self.btn_float, "Avería Flotador (Riesgo Desborde)", self.env.float_valve_broken)
        self._draw_btn(self.btn_burst, "Ruptura Mayor Tubería (30 L/min)", self.env.pipe_burst)
        self._draw_btn(self.btn_away, "Alternar Ausencia en Hogar", self.env.is_away)
        self._draw_btn(self.btn_refill, "Recargar Tinaco al 90%", False)
        self._draw_btn(self.btn_reset, "Reiniciar a las 02:00 hrs (Tecla R)", False)

        # Columna 2
        p2 = pygame.Rect(420, 95, 480, 685)
        pygame.draw.rect(self.screen, C_PANEL, p2, border_radius=12)
        pygame.draw.rect(self.screen, C_BORDER, p2, 1, border_radius=12)

        self.screen.blit(self.f_bold.render("NÚCLEO DE INFERENCIA DEL AGENTE (REAS / PAMA)", True, C_TEXT_MAIN), (440, 110))

        status_card = pygame.Rect(440, 140, 440, 95)
        card_col = C_RED_DANGER if decision["severity"] == "CRITICA" else (C_AMBER_WARN if decision["severity"] == "ADVERTENCIA" else C_BORDER)
        pygame.draw.rect(self.screen, (20, 24, 33), status_card, border_radius=8)
        pygame.draw.rect(self.screen, card_col, status_card, 2, border_radius=8)

        self.screen.blit(self.f_sub.render("ESTADO CLASIFICADO POR EL AGENTE:", True, C_TEXT_MUTED), (455, 150))
        self.screen.blit(self.f_big.render(decision["state"], True, card_col), (455, 170))
        self.screen.blit(self.f_mono.render(f"Regla Activada: {decision['rule_id']}", True, C_CYAN), (455, 210))

        exp_y = 255
        self.screen.blit(self.f_bold.render("Diagnóstico Causal Inferido:", True, C_TEXT_MAIN), (440, exp_y))
        exp_y += 22
        self._draw_wrapped_text(decision["diagnosis"], 440, exp_y, 440, C_TEXT_MUTED)

        exp_y += 55
        self.screen.blit(self.f_bold.render("Directiva / Acción de Mitigación:", True, C_TEXT_MAIN), (440, exp_y))
        exp_y += 22
        self._draw_wrapped_text(decision["action"], 440, exp_y, 440, C_TEXT_MAIN)

        exp_y += 75
        self.screen.blit(self.f_bold.render("Serie Temporal de Consumo Instantáneo (L/min)", True, C_TEXT_MAIN), (440, exp_y))
        exp_y += 25
        g_rect = pygame.Rect(440, exp_y, 440, 140)
        pygame.draw.rect(self.screen, (10, 14, 20), g_rect, border_radius=6)
        pygame.draw.rect(self.screen, C_BORDER, g_rect, 1, border_radius=6)

        points = []
        for i, val in enumerate(self.env.flow_history):
            gx = g_rect.x + (i * (g_rect.width / len(self.env.flow_history)))
            gy = g_rect.bottom - min(g_rect.height - 10, int((val / 35.0) * (g_rect.height - 10))) - 5
            points.append((gx, gy))
        if len(points) >= 2:
            pygame.draw.lines(self.screen, C_CYAN, False, points, 2)

        thresh_y = g_rect.bottom - int((0.5 / 35.0) * (g_rect.height - 10)) - 5
        pygame.draw.line(self.screen, C_RED_DANGER, (g_rect.x, thresh_y), (g_rect.right, thresh_y), 1)
        self.screen.blit(self.f_mono.render("Umbral R-02 (0.4 L/min)", True, C_RED_DANGER), (g_rect.x + 10, thresh_y - 14))

        # Columna 3
        p3 = pygame.Rect(920, 95, 420, 685)
        pygame.draw.rect(self.screen, C_PANEL, p3, border_radius=12)
        pygame.draw.rect(self.screen, C_BORDER, p3, 1, border_radius=12)

        self.screen.blit(self.f_bold.render("BITÁCORA DE INFERENCIAS Y ALERTAS", True, C_TEXT_MAIN), (940, 110))
        self.screen.blit(self.f_sub.render("Registro de eventos y trazabilidad del razonamiento", True, C_TEXT_MUTED), (940, 130))

        log_y = 160
        for stamp, msg, sev in self.decision_log:
            if log_y > p3.bottom - 45:
                break
            dot_col = C_RED_DANGER if sev == "CRITICA" else (C_AMBER_WARN if sev == "ADVERTENCIA" else C_CYAN)
            pygame.draw.circle(self.screen, dot_col, (945, log_y + 8), 4)
            self.screen.blit(self.f_mono.render(stamp, True, C_TEXT_MUTED), (958, log_y))
            
            m_text = msg if len(msg) < 46 else msg[:43] + "..."
            self.screen.blit(self.f_body.render(m_text, True, C_TEXT_MAIN), (958, log_y + 16))
            log_y += 40

    def _draw_btn(self, rect, text, active):
        col = (46, 60, 80) if active else (28, 33, 44)
        border_col = C_CYAN if active else C_BORDER
        pygame.draw.rect(self.screen, col, rect, border_radius=8)
        pygame.draw.rect(self.screen, border_col, rect, 1, border_radius=8)
        label_col = C_CYAN if active else C_TEXT_MUTED
        self.screen.blit(self.f_body.render(text, True, label_col), (rect.x + 12, rect.y + 8))

    def _draw_wrapped_text(self, text, x, y, max_w, color):
        words = text.split(" ")
        line = ""
        cur_y = y
        for w in words:
            test_line = line + w + " "
            if self.f_body.size(test_line)[0] > max_w:
                self.screen.blit(self.f_body.render(line, True, color), (x, cur_y))
                line = w + " "
                cur_y += 18
            else:
                line = test_line
        self.screen.blit(self.f_body.render(line, True, color), (x, cur_y))

if __name__ == "__main__":
    app = WaterSimulationApp()
    app.run()