import re
import serial
import serial.tools.list_ports
import PySimpleGUI as sg
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from math import floor
from datetime import datetime
import time

portas = [comport.device for comport in serial.tools.list_ports.comports()]

data_e_hora_atuais = datetime.now()
data_e_hora_em_texto = data_e_hora_atuais.strftime('%d/%m/%Y %H:%M')


def popup_select(the_list, select_multiple=False):
    layout = [[sg.Listbox(the_list, key='_LIST_', size=(45, len(the_list)),
                          select_mode='extended' if select_multiple else 'single', bind_return_key=True), sg.OK()]]
    window = sg.Window('Escolha a porta serial do arduino', layout=layout)
    event, values = window.read()
    window.close()
    del window
    if select_multiple or values['_LIST_'] is None:
        return values['_LIST_']
    else:
        return values['_LIST_'][0]


nbr = popup_select(portas)  # returns single number
# Serial arduino
conexao = serial.Serial("{}".format(nbr), 9600, timeout=0.0005)

# escala dos elementos da janela
tempo = 0
tara = float(0)
i = 0
j = 0
scale = 1
erro = False
x_vals_p = []
y_vals_p = []
x_vals_u = []
y_vals_u = []
x_vals_t = []
y_vals_t = []
setplist = []

var = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
last_var = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
last_secure_var = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
sample = 0
T_novo_ensaio = 0
duracao = 9999


def draw_figure(canvas, figure, loc=(0, 0)):
    figure_canvas_agg = FigureCanvasTkAgg(figure, canvas)
    figure_canvas_agg.draw()
    figure_canvas_agg.get_tk_widget().pack(side='top', fill='both', expand=1)
    return figure_canvas_agg

# ---Elementos do PySimpleGui---
sg.theme('Dark')

pid = [[sg.Text('Proprocional:')],
       [sg.Input(key='proprocional', size=(3 * scale, 1 * scale)), sg.Button('Ajustar', key='aplProporcional')],
       [sg.Text('Integral:')],
       [sg.Input(key='integral', size=(3 * scale, 1 * scale)), sg.Button('Ajustar', key='aplIntegral')],
       [sg.Text('Derivativa:')],
       [sg.Input(key='derivativa', size=(3 * scale, 1 * scale)), sg.Button('Ajustar', key='aplDerivativa')],
       [sg.Button('Ajustar todos os parametros')]]

ajuste = [[sg.Text('Temperatura alvo (C):')],
          [sg.Input(size=(12 * scale, 1 * scale), key='setpoint'), sg.Button('Ajustar')],
          [sg.Button('Ligar', size=(12 * scale, 1 * scale)), sg.Button('Novo Ensaio', size=(12 * scale, 1 * scale))],
          [sg.Button('Desligar', size=(12 * scale, 1 * scale)), sg.Text('Desligamento automatico:')],
          [sg.Button('Tara', size=(12 * scale, 1 * scale)), sg.Input(size=(12 * scale, 1 * scale), key = 'desl_A'), sg.Button('Ajustar', key = 'apl_desl_a')],
          [sg.Text('Tempo da perturbação:')],
          [sg.Input(size=(12 * scale, 1 * scale), key='tempo'), sg.Button('Aplicar perturbação na temperatura')]]

controle = [
    [sg.Frame('Controle', ajuste, vertical_alignment='c'), sg.Frame('Ajuste do PID', pid, vertical_alignment='t')]]

console = [[sg.Output(font=('arial', 8), size=(70 * scale, 15 * scale), key='output', echo_stdout_stderr=True)]]

graf_temperatura = [[sg.Canvas(size=(640, 480), key='gtemp')]]

graf_massa = [[sg.Canvas(size=(640, 480), key='gmass')]]

graf_umidade = [[sg.Canvas(size=(640, 480), key='gumi')]]

dados = [[sg.Text('Numero de pontos:'), sg.Input(key='pontos', size=(5 * scale, 1 * scale))],
         [sg.Button('Gerar dados de Temperatura', size=(12 * scale, 2 * scale))],
         [sg.Button('Gerar dados de Massa', size=(12 * scale, 2 * scale))],
         [sg.Button('Gerar dados de Umidade', size=(12 * scale, 2 * scale))],
         [sg.Button('Gerar dados de temperatura, massa e umidade', size=(12 * scale, 3 * scale))],
         [sg.Button('Limpar console', size=(12 * scale, 1 * scale))]]

layout = [[sg.Frame('', controle, vertical_alignment='c'), sg.Frame('Console', console, vertical_alignment='c'),
           sg.Frame('', dados, vertical_alignment='c')],
          [sg.Frame('Temperatura', graf_temperatura), sg.Frame('Massa', graf_massa), sg.Frame('Umidade', graf_umidade)],
          [sg.Text('_' * 70 * scale), sg.Button('Sair', size=(12 * scale, 1 * scale)), sg.Text('_' * 70 * scale)]]

layout = [[sg.Frame('', layout)]]

janela = sg.Window('Interface gráfica secador', layout, finalize=True, keep_on_top=True, element_justification='c', grab_anywhere=True,
                   location=(50, 10))

canvas_elemt = janela['gtemp']
canvas_elemm = janela['gmass']
canvas_elemu = janela['gumi']

canvast = canvas_elemt.TKCanvas
canvasm = canvas_elemm.TKCanvas
canvasu = canvas_elemu.TKCanvas

linewid = 2

fig1 = Figure(tight_layout=True)
fig1.set_figwidth(3.5 * scale)
fig1.set_figheight(3 * scale)
ax1 = fig1.add_subplot()
ax1.set_xlabel("Tempo")
ax1.set_ylabel("Temperatura")
ax1.grid()
ax1.plot(x_vals_t, y_vals_t, color='purple', label='Temperatura', linewidth=linewid)
ax1.plot(x_vals_t, setplist, color='red', label='Setpoint', linestyle='--')
ax1.legend()
fig_agg1 = draw_figure(canvast, fig1)

fig2 = Figure(tight_layout=True)
fig2.set_figwidth(3.5 * scale)
fig2.set_figheight(3 * scale)
ax2 = fig2.add_subplot()
ax2.set_xlabel("Tempo")
ax2.set_ylabel("Massa")
ax2.grid()
ax2.plot(x_vals_p, y_vals_p, color='purple', label='Massa', linewidth=linewid)
ax2.legend()
fig_agg2 = draw_figure(canvasm, fig2)

fig3 = Figure(tight_layout=True)
fig3.set_figwidth(3.5 * scale)
fig3.set_figheight(3 * scale)
ax3 = fig3.add_subplot()
ax3.set_xlabel("Tempo")
ax3.set_ylabel("Umidade")
ax3.grid()
ax3.plot(x_vals_u, y_vals_u, color='purple', label='Umidade', linewidth=linewid)
ax3.legend()
fig_agg3 = draw_figure(canvasu, fig3)
# ---Elementos do PySimpleGui---

# ---Inicialização da janela---
while True:
    event, values = janela.read(timeout=800)

    if event == sg.WIN_CLOSED or event == 'Sair':
        conexao.write(b's0')
        break
    leitura = conexao.readline()
    if len(leitura) > 0:
        leiturad = leitura.decode()
        var = re.split(',', leiturad)
    try:
        pwm = int(var[0])
    except:
        pwm = int(last_var[0])
        erro = True
    else:
        last_var[0] = var[0]
    try:
        temperatura = float(var[1])
    except:
        temperatura = float(last_var[1])
        erro = True
    else:
        last_var[1] = var[1]
    try:
        peso = float(var[2]) - tara
    except:
        peso = float(last_var[2]) - tara
        erro = True
    else:
        last_var[2] = var[2]
    try:
        umidade = float(var[3])
    except:
        umidade = float(last_var[3])
        erro = True
    else:
        last_var[3] = var[3]
    try:
        setpoint = float(var[4])
    except:
        setpoint = float(last_var[4])
        erro = True
    else:
        last_var[4] = var[4]
    try:
        tempogr = (int(var[8]) - T_novo_ensaio) / 60
    except:
        tempogr = (int(last_var[8]) - T_novo_ensaio) / 60
        erro = True
    else:
        last_var[8] = var[8]
        erro = False
    if duracao <= tempogr:
        conexao.write(b's0')
        print("O controle foi desligado.")
        janela['Ligar'].update(disabled=False)
        janela['Desligar'].update(disabled=True)
        try:
            pontos = int(values['pontos'])
        except:
            pontos = len((x_vals_t))
        if pontos > len(x_vals_t):
            pontos = len((x_vals_t))
        templist = y_vals_t[::floor(len(y_vals_t) // pontos)]
        masslist = y_vals_p[::floor(len(y_vals_p) // pontos)]
        umidlist = y_vals_u[::floor(len(y_vals_u) // pontos)]
        timelist = x_vals_t[::floor(len(x_vals_t) // pontos)]
        print('Gerando dados...')
        time.sleep(1)
        print('')
        print('Temperatura(*C), Massa(g), umidade(%), Tempo(s)')
        for i in range(len(templist)):
            print(templist[i], ',', masslist[i], ',', umidlist[i], ',', timelist[i])
        print('')
        with open('dados_secagem.txt', 'w') as arquivo:
            arquivo.write('' + '\n')
            arquivo.write(data_e_hora_em_texto + '\n')
            arquivo.write('Temperatura(*C)    Massa(g)    umidade(%)    Tempo(s)' + '\n')
            for valor in range(len(templist)):
                arquivo.write(str(templist[valor]) + '                ' + str(masslist[valor]) + '         ' + str(
                    umidlist[valor]) + '          ' + str(timelist[valor]) + '\n')
        duracao = 9999

    t1 = time.time()
    t0 = 0
    if t1 - t0 > 1 and tempogr != 0 and erro == False and sample - temperatura < 3 and len(var) == 10:
        t0 = t1
        i = i + 1
        intervalo = 100
        x_vals_t.append(tempogr)
        y_vals_t.append(temperatura)
        setplist.append(setpoint)

        x_vals_p.append(tempogr)
        y_vals_p.append(peso)

        x_vals_u.append(tempogr)
        y_vals_u.append(umidade)

        if len(x_vals_t) > intervalo:
            ax1.clear()
            ax1.grid()
            ax1.set_xlabel("Tempo(min)")
            ax1.set_ylabel("Temperatura(*C)")
            ax1.plot(x_vals_t[::len(x_vals_t) // intervalo], y_vals_t[::len(y_vals_t) // intervalo], color='purple',
                     label='Temperatura', linewidth=linewid)
            ax1.plot(x_vals_t[::len(x_vals_t) // intervalo], setplist[::len(setplist) // intervalo], color='red',
                     label='Setpoint', linestyle='--')
            ax1.legend()
            fig_agg1.draw()

            ax2.clear()
            ax2.grid()
            ax2.set_xlabel("Tempo(min)")
            ax2.set_ylabel("Massa(g)")
            ax2.plot(x_vals_p[::len(x_vals_p) // intervalo], y_vals_p[::len(y_vals_p) // intervalo], color='purple',
                     label='Massa', linewidth=linewid)
            ax2.legend()
            fig_agg2.draw()

            ax3.clear()
            ax3.grid()
            ax3.set_xlabel("Tempo(min)")
            ax3.set_ylabel("Umidade(%)")
            ax3.plot(x_vals_u[::len(x_vals_u) // intervalo], y_vals_u[::len(y_vals_u) // intervalo], color='purple',
                     label='Umidade', linewidth=linewid)
            ax3.legend()
            fig_agg3.draw()

        if len(x_vals_t) <= intervalo:
            ax1.clear()
            ax1.grid()
            ax1.set_xlabel("Tempo(min)")
            ax1.set_ylabel("Temperatura(*C)")
            ax1.plot(x_vals_t[::1], y_vals_t[::1], color='purple', label='Temperatura', linewidth=linewid)
            ax1.plot(x_vals_t[::1], setplist[::1], color='red', label='Setpoint', linestyle='--')
            ax1.legend()
            fig_agg1.draw()

            ax2.clear()
            ax2.grid()
            ax2.set_xlabel("Tempo(min)")
            ax2.set_ylabel("Massa(g)")
            ax2.plot(x_vals_p[::1], y_vals_p[::1], color='purple', label='Massa', linewidth=linewid)
            ax2.legend()
            fig_agg2.draw()

            ax3.clear()
            ax3.grid()
            ax3.set_xlabel("Tempo(min)")
            ax3.set_ylabel("Umidade(%)")
            ax3.plot(x_vals_u[::1], y_vals_u[::1], color='purple', label='Umidade', linewidth=linewid)
            ax3.legend()
            fig_agg3.draw()

    sample = temperatura
    if event == 'Aplicar perturbação na temperatura':
        tempo = int(values['tempo'])
        print('Será aplicado uma perturbação de {} segundos na temperatura.'.format(tempo))

    t00 = 0
    if t1 - t00 > 1:
        t00 = t1
        for k in range(tempo):
            perturbacao = float(var[4])
            n = 't' + str(perturbacao + 40)
            conexao.write(n.encode())
            tempo = tempo - 1
            if tempo == 0:
                n = 't' + str(var[4])
                conexao.write(n.encode())

    if event == 'aplProporcional':
        p = values['proprocional']
        pw = 'p' + str(p)
        print(pw)
        conexao.write(pw.encode())
        print('O parâmetro proporcional foi ajustado para o valor de {}'.format(p))

    if event == 'aplIntegral':
        ii = values['integral']
        iw = 'i' + str(ii)
        conexao.write(iw.encode())
        print('O parâmetro integral foi ajustado para o valor de {}'.format(ii))

    if event == 'aplDerivativa':
        d = values['derivativa']
        dw = 'd' + str(d)
        conexao.write(dw.encode())
        print('O parâmetro derivativo foi ajustado para o valor de {}'.format(d))

    if event == 'Ajustar todos os parametros':
        p = values['proprocional']
        pw = 'p' + str(p)
        ii = values['integral']
        iw = 'i' + str(ii)
        d = values['derivativa']
        dw = 'd' + str(d)
        conexao.write(pw.encode())
        conexao.write(iw.encode())
        conexao.write(dw.encode())
        print(
            'Os parâmetros proporcional, integral e derivativo foram  ajustados para os valores: {}, {} e {} respectivamente.'.format(
                p, ii, d))

    if event == 'Ligar':
        if pwm > 0:
            print("O controle já está ligado!")
        else:
            print("O controle foi ligado.")
            conexao.write(b'r')
            janela['Ligar'].update(disabled=True)
            janela['Desligar'].update(disabled=False)

    if event == 'Novo Ensaio':
        try:
            T_novo_ensaio = int(var[8])
        except:
            T_novo_ensaio = int(last_var[8])
        if T_novo_ensaio < 0:
            T_novo_ensaio = 0
        print(T_novo_ensaio)
        x_vals_p.clear()
        y_vals_p.clear()
        x_vals_u.clear()
        y_vals_u.clear()
        x_vals_t.clear()
        y_vals_t.clear()
        setplist.clear()

        ax1.clear()
        ax1.grid()
        ax2.clear()
        ax2.grid()
        ax3.clear()
        ax3.grid()
    if event == 'apl_desl_a':
        try:
            duracao = float(values['desl_A'])
            print('A duração da secagem foi ajustada para {} minutos.'.format(duracao))
        except:
            print('Não foi possivel ajustar. Por favor, tente novamente.')
            duracao = 9999


    if event == "Desligar":
        conexao.write(b's0')
        print("O controle foi desligado.")
        janela['Ligar'].update(disabled=False)
        janela['Desligar'].update(disabled=True)

    if event == 'Ajustar':
        setpoint = values['setpoint']
        n = 't' + str(setpoint)
        conexao.write(n.encode())
        print('A temperatura  do setpoint foi ajustada para {} graus.'.format(setpoint))

    if event == 'Tara':
        tara = float(var[2])
        x_vals_p.clear()
        y_vals_p.clear()
        x_vals_u.clear()
        y_vals_u.clear()
        x_vals_t.clear()
        y_vals_t.clear()
        setplist.clear()

        ax1.clear()
        ax1.grid()
        ax2.clear()
        ax2.grid()
        ax3.clear()
        ax3.grid()

        print('A tara foi ajustada para {} gramas.'.format(tara))

    if event == 'Limpar console':
        janela.FindElement('output').Update('')

    if event == 'Gerar dados de Temperatura':
        try:
            pontos = int(values['pontos'])
        except:
            pontos = len((x_vals_t))
        if pontos > len(x_vals_t):
            pontos = len((x_vals_t))
        templist = y_vals_t[::floor(len(y_vals_t) // pontos)]
        timelist = x_vals_t[::floor(len(x_vals_t) // pontos)]
        print('Gerando dados de temperatura...')
        time.sleep(1)
        print('')
        print('Temperatura(°C),Tempo(s)')
        for i in range(len(templist)):
            print(templist[i], ',', round(timelist[i], 2))
        print('')
        with open('dados_secagem.txt', 'w') as arquivo:
            arquivo.write('' + '\n')
            arquivo.write(data_e_hora_em_texto + '\n')
            arquivo.write('Temperatura(°C)    Tempo(s)' + '\n')
            for valor in range(len(templist)):
                arquivo.write(str(templist[valor]) + '                ' + str(round(timelist[valor], 2)) + '\n')

    if event == 'Gerar dados de Massa':
        try:
            pontos = int(values['pontos'])
        except:
            pontos = len((x_vals_t))
        if pontos > len(x_vals_t):
            pontos = len((x_vals_t))
        masslist = y_vals_p[::floor(len(y_vals_p) // pontos)]
        timelist = x_vals_t[::floor(len(x_vals_t) // pontos)]
        print('Gerando dados de massa...')
        time.sleep(1)
        print('')
        print('Massa(g),Tempo(s)')
        for i in range(len(masslist)):
            print(round(masslist[i], 2), ',', round(timelist[i], 2))
        print('')
        with open('dados_secagem.txt', 'w') as arquivo:
            arquivo.write('' + '\n')
            arquivo.write(data_e_hora_em_texto + '\n')
            arquivo.write('Massa(g)    Tempo(s)' + '\n')
            for valor in range(len(masslist)):
                arquivo.write(str(round(masslist[valor], 2)) + '         ' + str(round(timelist[valor], 2)) + '\n')

    if event == 'Gerar dados de Umidade':
        try:
            pontos = int(values['pontos'])
        except:
            pontos = len((x_vals_t))
        if pontos > len(x_vals_t):
            pontos = len((x_vals_t))
        umidlist = y_vals_u[::floor(len(y_vals_u) // pontos)]
        timelist = x_vals_t[::floor(len(x_vals_t) // pontos)]
        print('Gerando dados de umidade...')
        time.sleep(1)
        print('')
        print('Umidade(%)   Tempo(s)')
        for i in range(len(umidlist)):
            print(umidlist[i], ',', round(timelist[i], 2))
        print('')
        with open('dados_secagem.txt', 'w') as arquivo:
            arquivo.write('' + '\n')
            arquivo.write(data_e_hora_em_texto + '\n')
            arquivo.write('Umidade(%)    Tempo(s)' + '\n')
            for valor in range(len(umidlist)):
                arquivo.write(str(umidlist[valor]) + '          ' + str(round(timelist[valor], 2)) + '\n')
    if event == 'Gerar dados de temperatura, massa e umidade':
        try:
            pontos = int(values['pontos'])
        except:
            pontos = len((x_vals_t))
        if pontos > len(x_vals_t):
            pontos = len((x_vals_t))
        templist = y_vals_t[::floor(len(y_vals_t) // pontos)]
        masslist = y_vals_p[::floor(len(y_vals_p) // pontos)]
        umidlist = y_vals_u[::floor(len(y_vals_u) // pontos)]
        timelist = x_vals_t[::floor(len(x_vals_t) // pontos)]
        print('Gerando dados...')
        time.sleep(1)
        print('')
        print('Temperatura(*C), Massa(g), umidade(%), Tempo(s)')
        for i in range(len(templist)):
            print(templist[i], ',', round(masslist[i], 2), ',', umidlist[i], ',', round(timelist[i], 2))
        print('')
        with open('dados_secagem.txt', 'w') as arquivo:
            arquivo.write('' + '\n')
            arquivo.write(data_e_hora_em_texto + '\n')
            arquivo.write('Temperatura(*C)    Massa(g)    umidade(%)    Tempo(s)' + '\n')
            for valor in range(len(templist)):
                arquivo.write(str(templist[valor]) + '                ' + str(round(masslist[valor], 2)) + '         ' +
                              str(umidlist[valor]) + '          ' + str(round(timelist[valor], 2)) + '\n')
