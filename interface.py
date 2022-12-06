import re
import serial.tools.list_ports
import PySimpleGUI as sg
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from math import floor
from datetime import datetime
import time

portas = [comport.device for comport in serial.tools.list_ports.comports()] #Procura as portas seriais do sistema

data_e_hora_atuais = datetime.now() #Pega a hora atual
data_e_hora_em_texto = data_e_hora_atuais.strftime('%d/%m/%Y %H:%M') #Pega a hora atual em texto

#função para escolher a porta serial
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

nbr = popup_select(portas) #Define a porta escolhida na função anterior
conexao = serial.Serial("{}".format(nbr), 9600, timeout=0.0005) #Tenta se conectar ao arduino atravez da porta escolhida

tempo = 0 #Tempo da perturbação
tara = float(0) #Tara da balança
scale = 3 #Escala da aplicação
erro = False #Flag de erro

#Listas de dados para plotagem de graficos
x_vals_p = []
y_vals_p = []
x_vals_u = []
y_vals_u = []
x_vals_t = []
y_vals_t = []
setplist = []

#Listas de variaveis de dados recebidas do arduino
var = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] #Lista recebida no momento
last_var = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] #Lista anterior

sample = 0 #Variavel que guarda o valor da temperatura
T_novo_ensaio = 0 #Variavel para iniciar um novo ensaio de secagem
duracao = 9999 #Variavel para configurar o desligamento automatico

#Função para definir o convas de plotagem dos graficos
def draw_figure(canvas, figure, loc=(0, 0)):
    figure_canvas_agg = FigureCanvasTkAgg(figure, canvas)
    figure_canvas_agg.draw()
    figure_canvas_agg.get_tk_widget().pack(side='top', fill='both', expand=1)
    return figure_canvas_agg

# ---Elementos do PySimpleGui---
sg.theme('Dark')

# Construção do Frame Ajuste do PID
pid = [[sg.Text('Proprocional:')],
       [sg.Input(key='proprocional', size=(3 * scale, 1 * scale)), sg.Button('Ajustar', key='aplProporcional')],
       [sg.Text('Integral:')],
       [sg.Input(key='integral', size=(3 * scale, 1 * scale)), sg.Button('Ajustar', key='aplIntegral')],
       [sg.Text('Derivativa:')],
       [sg.Input(key='derivativa', size=(3 * scale, 1 * scale)), sg.Button('Ajustar', key='aplDerivativa')],
       [sg.Button('Ajustar todos os parametros')]]

# Construção do Frame de Controle
ajuste = [[sg.Text('Temperatura alvo (C):')],
          [sg.Input(size=(12 * scale, 1 * scale), key='setpoint'), sg.Button('Ajustar')],
          [sg.Button('Ligar', size=(12 * scale, 1 * scale)), sg.Button('Novo Ensaio', size=(12 * scale, 1 * scale))],
          [sg.Button('Desligar', size=(12 * scale, 1 * scale)), sg.Text('Desligamento automatico:')],
          [sg.Button('Tara', size=(12 * scale, 1 * scale)), sg.Input(size=(12 * scale, 1 * scale), key = 'desl_A'), sg.Button('Ajustar', key = 'apl_desl_a')],
          [sg.Text('Tempo da perturbação:')],
          [sg.Input(size=(12 * scale, 1 * scale), key='tempo'), sg.Button('Aplicar perturbação na temperatura')]]

# Construção do Frame que contem o Controle e o Ajuste do PID
controle = [
    [sg.Frame('Controle', ajuste, vertical_alignment='c'), sg.Frame('Ajuste do PID', pid, vertical_alignment='t')]]

# Construção do console de comunicação
console = [[sg.Output(font=('arial', 8), size=(70 * scale, 15 * scale), key='output', echo_stdout_stderr=True)]]

#Construção do grafico da temperatura
graf_temperatura = [[sg.Canvas(size=(640, 480), key='gtemp')]]

#Construção do grafico da massa
graf_massa = [[sg.Canvas(size=(640, 480), key='gmass')]]

#Construção do grafico da umidade
graf_umidade = [[sg.Canvas(size=(640, 480), key='gumi')]]

#Construção do Frame de gerar dados
dados = [[sg.Text('Numero de pontos:'), sg.Input(key='pontos', size=(5 * scale, 1 * scale))],
         [sg.Button('Gerar dados de Temperatura', size=(12 * scale, 2 * scale))],
         [sg.Button('Gerar dados de Massa', size=(12 * scale, 2 * scale))],
         [sg.Button('Gerar dados de Umidade', size=(12 * scale, 2 * scale))],
         [sg.Button('Gerar dados de temperatura, massa e umidade', size=(12 * scale, 3 * scale))],
         [sg.Button('Limpar console', size=(12 * scale, 1 * scale))]]

#Construção do layout da aplicação
layout = [[sg.Frame('', controle, vertical_alignment='c'), sg.Frame('Console', console, vertical_alignment='c'),
           sg.Frame('', dados, vertical_alignment='c')],
          [sg.Frame('Temperatura', graf_temperatura), sg.Frame('Massa', graf_massa), sg.Frame('Umidade', graf_umidade)],
          [sg.Text('_' * 70 * scale), sg.Button('Sair', size=(12 * scale, 1 * scale)), sg.Text('_' * 70 * scale)]]

#Construção do Frame ao redor do layout
layout = [[sg.Frame('', layout)]]

#Construção da janela da aplicação
janela = sg.Window('Interface gráfica secador', layout, finalize=True, keep_on_top=True, element_justification='c', grab_anywhere=True,
                   location=(50, 10))

#Definição dos elementos do canvas para os graficos
canvas_elemt = janela['gtemp'] #grafico da temperatura
canvas_elemm = janela['gmass'] #grafico da massa
canvas_elemu = janela['gumi'] #grafico da umidade

canvast = canvas_elemt.TKCanvas #Construção do canvas de temperatura
canvasm = canvas_elemm.TKCanvas #Contrução do canvas de massa
canvasu = canvas_elemu.TKCanvas #Construção do canvas de umidade

linewid = 2 #Grossura da linha de plotagem

#Plotagem do grafico de temperatura
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

#Plotagem do grafico de massa
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

#Plotagem do grafico de umidade
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

# ---Inicialização dos eventos da aplicação---
while True:
    event, values = janela.read(timeout=800)

    #Sair da aplicação
    if event == sg.WIN_CLOSED or event == 'Sair':
        conexao.write(b's0')
        break

    #Leitura dos dados do arduino
    leitura = conexao.readline() #Recebe os dados brutos
    if len(leitura) > 0: #Verifica se recebeu algum dado
        leiturad = leitura.decode() #Transforma os dados de binario para texto
        var = re.split(',', leiturad) #Divide os dados recebidos com virgulas, e guarda em uma lista

    #Codigo para guardar cada dado em sua propria lista, com um sistema para garantir que tudo esteja em ordem
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

    # Monitora, controla e gera os dados quando for habilidado o controle automatico
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

    t1 = time.time() #Tempo atual
    t0 = 0
    #Verifica se tudo algo deu errado, e caso contrario guarda os dados na lista para plotagem
    if t1 - t0 > 1 and tempogr != 0 and erro == False and sample - temperatura < 3 and len(var) == 10:
        t0 = t1
        intervalo = 100 #Intervalo de pontos que vão aparecer no gráfico
        x_vals_t.append(tempogr)
        y_vals_t.append(temperatura)
        setplist.append(setpoint)

        x_vals_p.append(tempogr)
        y_vals_p.append(peso)

        x_vals_u.append(tempogr)
        y_vals_u.append(umidade)

        #Quando o numero de pontos passar o numero definido no intervalo, será usado essa função para usar 100 pontos espaçados da lista
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

    sample = temperatura #Guarda o valor atual da temperatura

    #Aplicação de uma perturbação(aumento do setpoint) temporario.
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
    # Ajuste do parametro proporcional do PID
    if event == 'aplProporcional':
        p = values['proprocional']
        pw = 'p' + str(p)
        print(pw)
        conexao.write(pw.encode())
        print('O parâmetro proporcional foi ajustado para o valor de {}'.format(p))

    # Ajuste do parametro integral do PID
    if event == 'aplIntegral':
        ii = values['integral']
        iw = 'i' + str(ii)
        conexao.write(iw.encode())
        print('O parâmetro integral foi ajustado para o valor de {}'.format(ii))

    # Ajuste do parametro derivativo do PID
    if event == 'aplDerivativa':
        d = values['derivativa']
        dw = 'd' + str(d)
        conexao.write(dw.encode())
        print('O parâmetro derivativo foi ajustado para o valor de {}'.format(d))

    # Ajuste de todos os parametros do PID
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

    # Ligar o controle
    if event == 'Ligar':
        if pwm > 0:
            print("O controle já está ligado!")
        else:
            print("O controle foi ligado.")
            conexao.write(b'r')
            janela['Ligar'].update(disabled=True)
            janela['Desligar'].update(disabled=False)

    # Novo ensaio de secagem (apaga todos os dados de secagem atuais e começa tudo de novo)
    if event == 'Novo Ensaio':
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
        print('Gerando dados do ultimo ensaio...')
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

        try:
            T_novo_ensaio = int(var[8])
        except:
            T_novo_ensaio = int(last_var[8])
        if T_novo_ensaio < 0:
            T_novo_ensaio = 0

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

        #Definir a duração da secagem automatica
    if event == 'apl_desl_a':
        try:
            duracao = float(values['desl_A'])
            print('A duração da secagem foi ajustada para {} minutos.'.format(duracao))
        except:
            print('Não foi possivel ajustar. Por favor, tente novamente.')
            duracao = 9999

    #Desligar o controle
    if event == "Desligar":
        conexao.write(b's0')
        print("O controle foi desligado.")
        janela['Ligar'].update(disabled=False)
        janela['Desligar'].update(disabled=True)

    #Ajustar a temperatura do setpoint
    if event == 'Ajustar':
        setpoint = values['setpoint']
        n = 't' + str(setpoint)
        conexao.write(n.encode())
        print('A temperatura  do setpoint foi ajustada para {} graus.'.format(setpoint))

    #Tarar a balança
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

    #Limpar o console de dados
    if event == 'Limpar console':
        janela.FindElement('output').Update('')

    #Gerar dados da temperatura(no console e em um arquivo txt)
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

    # Gerar dados da massa(no console e em um arquivo txt)
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

    # Gerar dados da umidade(no console e em um arquivo txt)
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

    # Gerar dados da temperatura, massa e umidade(no console e em um arquivo txt)
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
