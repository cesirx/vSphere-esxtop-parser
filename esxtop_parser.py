#Script to parse esxtop batch output and plot stats
#
#Requirements:
#### Script auto discovers VMs in CSV file only if they are named according to InfraV naming conventions (at least, VM name must start with the string "VM_")
#
#Launching esxtop in bath mode:
# #ie, "esxtop -b -n 150 -d 2 -c /superFiltered > ./CPUshares_1to1_14vCPUVM_v0.2.csv"
#
# Tested in vSphere 6.5
#
# v0.2 by Cesar Ortega (Telefonica InfraV) cesar.ortegaroman@telefonica.com

from pathlib import Path
import numpy as np
import argparse
import re
import pandas as pd
import matplotlib.pyplot as plt
import random

def parse_arguments():
    """Process input arguments."""

    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="ESXTOP batch mode output file (csv) to parse. Must be stored with python program.")
    parser.add_argument('--system', help='display system processes (currently only "etherswitch")', action="store_true")

    return parser.parse_args()

def check_file(filename):
    """Build and check provided filename.
    
    Parameters
    ----------
    filename : string
        filename passed as argument
    Returns
    -------
    csv
        filename path
    """

    csv = Path.cwd() / filename    #Build CSV file path

    if not csv.exists():
        print("The file does not exist.")
        exit()
    else:
        return csv

def extract_vms_and_stats(df, system=''):
    """Get VMs and Stats available in input dataframe file.
    
    Parameters
    ----------
    df : dataframe
        Dataframe built from input CSV file
    Returns
    -------
    vms
        list of VMs found in input dataframe
    stats
        list of stats found in input dataframe
    """

    vms = []
    stats = []

    if system:
        pattern = re.compile(r'(helper).*(etherswitchHelper).*\\(.*)')
    else:
        pattern = re.compile(r'\\\\.*\\(.*)\(.*:(VM_[A-Za-z_0-9-]+).*\)\\(.*)')
        #Uncommented the following line (and commend the previous one) when plottig vmnic interfaces 
        #pattern = re.compile(r'\\\\.*\\(.*)\(.*:(VM_[A-Za-z_0-9-]+|vmnic[0-9]+)\)\\(.*)')

    for col in df.columns:
        m = pattern.search(col)
        if m:
            if (m.group(2) not in vms) and ("VM_DRIVER_QUEUE" not in m.group(2)) and ("VM_ASYNCIO_QUEUE" not in m.group(2)):    # Store VMs but remove hypervisor matching processes
                vms.append(m.group(2))  #Add only new VMs no the vm list
            if (m.group(1) +'\\'+ m.group(3)) not in stats:
                stats.append(m.group(1) +'\\'+ m.group(3))    #Add only new Stats to the stat list

    return vms, stats

def vm_menu(vms):
    """Present a menu where user can select the desired VMs to plot.
    
    Parameters
    ----------
    vms : list
        List of VMs found out in esxtop
    Returns
    -------
    selected
        list of selected VMs to plot
    """
    
    selected = []  
    print(30 * "-", "Select VMs to plot", 30 * "-")
    print()
    for i in range(len(vms)):
        print(str(i) + ". " + vms[i])
    print()
    choice = (input("Enter VM indexes separated by commas [0-" + str(len(vms) - 1) + "] (type letter \"a\" to select all): "))  #Get user input in csv format and user ',' as delimiter to store each value in a list
    if choice == "a":
        print("All VMs selected")
        choice = list(range(0,len(vms)))    # Añadir todos los indices a la variable "choice"
        print(choice)
    else:
        print("Not all selected")
        choice = choice.split(',')
        choice = list(map(int, choice))    # Using map() to perform conversion of each element to integer

    for j in choice:
        selected.append(vms[j])

    return selected
  

def stat_menu(stats):
    """Present a menu where user can select the desired esxtop statistics to plot.
    
    Parameters
    ----------
    stats : list
        List of Stats found out in esxtop
    Returns
    -------
    selected
        list of selected Stats to plot
    """

    selected = []
    printed_groups = []
    print()
    print(30 * "-", "Select Stats to plot", 30 * "-")
    print()
    for i in range(len(stats)):
        if stats[i].split('\\')[0] not in printed_groups:
            printed_groups.append(stats[i].split('\\')[0])
            print()
            print('**** '+ stats[i].split('\\')[0]+ ' ****')
            print()
        print(str(i) + ". " + stats[i].split('\\')[1])
    print()
    choice = (input("Enter Stat indexes separated by commas [0-"+str(len(stats)-1) +"]: ")).split(',')     #Get user input in csv format and user ',' as delimiter to store each value in a list
    choice = list(map(int, choice))    # Using map() to perform conversion of each element to integer
    for j in choice:
        selected.append(stats[j])

    return selected


def plotter(df,vms,stats):
    """Function that plots the selected Stat for the selected VMs.

    Parameters
    ----------
    df : dataframe
        List of Stats found out in esxtop
    vms : list
        list of selected VMs to plot
    stats : list
        list of selected Stats to plot
    """
    
    avg_count = 0
    plot_type = 1
    s = ""

    if (len(stats) == 1) and (len(vms)>1):
        while True:
            print()
            print()
            print("How would you like to display the selected counter?")
            print()
            print("1) Not aggregated (plot one line per VM)")
            print("2) Aggregated (summation)")
            print("3) Aggregated (average)")
            print()
            try:
                plot_type = int(input("Enter your choice: "))
            except ValueError:
                print("Value not in range!")
                continue

            if plot_type in {1,2,3}:
                df['extra_col'] = "0.0"
                df['extra_col'] = df['extra_col'].astype(float)
                break
            else:
                continue

    print("plot_type {}".format(plot_type))
    #Special plotting items for certain Stats
    if '% Ready' in stats:
        plt.hlines(10,0,len(df.index),linestyles='dashed',label='Max. % Ready')    #Ready time should not exceed 10% (should be better used in a dedicated Ready Plot with all vCPUs)
    if '% CoStop' in stats:
        plt.hlines(3,0,len(df.index),linestyles=':',label='Max. % CoStop')        #CosTop value should not exceed 3%
  

    for v in vms:
        aggregated_sum = 0
        for t in stats:
            print(t)
            s = (t.split('\\'))[1]

            #Specific regex pattern matching each type of metric    
            if 'Group Cpu' in t:
                pattern = re.compile(r'.*\\'+(t.split('\\'))[0]+'\(.*'+ v +'\).*' + s)
            elif 'Vcpu' in t:
                pattern = re.compile(r'.*\\'+(t.split('\\'))[0] +'\(.*'+ v +':.*:vmx-(vcpu-[0-9]+).*' + s)
            elif 'Group Memory' in t:
                pattern = re.compile(r'.*\\'+(t.split('\\'))[0]+'\(.*'+ v +'\).*' + s)
            elif 'Network Port' in t:
                if 'Average Packet Size' in t:
                    #stat value contains "()" which must be escaped for the following regex to work: ie, "Average Packet Size  Transmitted (Bytes)"
                    s = s.replace("(","\(")
                    s = s.replace(")","\)")
                    pattern = re.compile(r'()'+v+'(\.eth[0-9]).*' + s)
                else:
                    pattern = re.compile(r'.*\\'+(t.split('\\'))[0]+'\(.*:()'+ v +'(.*)\)\\\\' + s)
                    #Uncomment the following line to also display SRIOV interfaces.
                    #Keep in mind that esxtop does not show statistics about these sort of interfaces.
                    #pattern = re.compile(r'.*\\'+(t.split('\\'))[0]+'\(.*:(SRIOV-)*'+ v +'(.*)\)\\\\' + s)
            elif 'Virtual Disk' in t:
                pattern = re.compile(r'.*\\'+(t.split('\\'))[0]+'\(.*'+ v +'\)(.*)' + s)
            elif "helper" in t:
                pattern = re.compile(r'(helper).*(etherswitchHelper).*\\'+s)
                
            for col in df.columns:
                m = pattern.search(col)
                if m:
                    line_style=''
                    if 'Vcpu' in t:
                        label = v + ' ' + m.group(1) + ' ' + s
                        if 'Physical Cpu' in s:
                            line_style = 'o'
                            plt.yticks(np.arange(0,56,1))   #np.arange will return an evenly spaced values within the given interval
                    elif 'Network Port' in t:
                        if m.group(1):
                            label = m.group(1) + v + m.group(2) + ' ' + s
                        else:
                            label = v + m.group(2) + ' ' + s
                    elif 'Virtual Disk' in t:
                        label = v + m.group(1) + ' ' + s
                    else:
                        label = v + ' ' + s

                        #A new column containing aggregated %Run of each VM. Comment if not required
                        #if s == '% Run':
                        #    df['RUN_Total'] += df[col]

                    if plot_type == 1:
                        plt.plot(df[col], label=label, marker=line_style)
                    elif plot_type == 2:
                        df['extra_col'] += df[col]
                    elif plot_type == 3:
                        print(df[col].dtypes)
                        df['extra_col'] += df[col]
                        avg_count += 1

                    #The following optional lines draw an arrow with an informational text at a random location of each line. Comment them if not required
                    #random_x=random.randint(0,df[col].size-1)
                    #plt.annotate(s, xy=(random_x, df[col].iloc[random_x]), xytext=(random_x, df[col].iloc[random_x] + 250),arrowprops=dict(facecolor='black', shrink=0.05))

    if plot_type == 2:
        plt.title('SUMMATION')
        label = s
        plt.plot(df['extra_col'], label=label, marker=line_style)
        del df['extra_col']
    elif plot_type == 3:
        plt.title('AVERAGE')
        label = s
        df['extra_col'] = df['extra_col'] / avg_count
        plt.plot(df['extra_col'], label=label, marker=line_style)
        del df['extra_col']

    #The following 2 lines provide meaningful information only when plotting %Run time of several VMs
    #Comment when the plot does not require them
    #plt.plot(df['RUN_Total'])
    #plt.hlines(5600,0,len(df.index),linestyles=':',label='56vCPU * 100%')

    plt.legend(loc='best', prop={'size': 6})
    #plt.legend(bbox_to_anchor=(1, 0), loc="lower right", prop={'size': 7})
    plt.xlabel('time')
    #plt.ylabel('pCPU')
    #plt.title('VM_Ubuntu_Benchmark_A with LatencySensitivity=High (running in a 56pCPU host)')
    #plt.title(str(s) + ' sum: ' + str(aggregated_sum))
    plt.grid()
    plt.show()  
    
def main():
    """Main script function."""
    
    args = parse_arguments() 
    csv_file = check_file(args.filename)
    dataframe = pd.read_csv(csv_file)   #Read CSV content
    vm_list, stat_list = extract_vms_and_stats(dataframe, args.system)   #Extract all VMs and Stats from CSV file

    while True:
        selected_vms = vm_menu(vm_list) #Print VM menu and get user choice
        selected_stats = stat_menu(stat_list)   #Print Stats menu and get user choice
        plotter(dataframe,selected_vms,selected_stats)  #Based on user selection, get matching columns to plot

if __name__ == '__main__':
    main()

