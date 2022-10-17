#!/usr/local/bin/python3
import os, sys, time, subprocess, re
import server
import signal
from datetime import datetime
import numpy as np
from scipy import stats

Procs = [None] * 1024

class Lat(object):

    def __init__(self, fileName):
        f = open(fileName, 'rb')
        a = np.fromfile(f, dtype=np.uint64)
        self.reqTimes = a.reshape((int(a.shape[0]/3.0), 3))
        f.close()

    def parseQueueTimes(self):
        return self.reqTimes[:, 0]
    
    def parseSvcTimes(self):
        return self.reqTimes[:, 1]
    
    def parseSojournTimes(self):
        return self.reqTimes[:, 2]

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def exec_cmd(cmd, index = 0, wait = True):
    global Procs
    print('CMD: ', cmd)
    p1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE, shell=True, close_fds=True, preexec_fn=os.setsid)
    Procs[index] = p1
    if wait:
        p1.wait()
    return p1

def parallel_cmd(cmd, num, wait = True):
    global Procs
    for i in range(0, num):
        real_cmd = '%s %d' % (cmd, i)
        print('CMD: ', real_cmd)
        p = subprocess.Popen(real_cmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE, shell=True, close_fds=True, preexec_fn=os.setsid)
        Procs[i] = p
    for i in range(0, num):
        if wait:
            Procs[i].wait()
    return Procs[:num]

def find_str(pattern, string):
    pat = re.compile(pattern)
    return pat.findall(string)[0].strip()

def find_str2(pattern, string):
    pat = re.compile(pattern)
    return pat.findall(string)[-1]

def split_str(string, char = ' '):
    return filter(lambda x:x, string.split(char))

def b2s(s):
    return str(s, encoding = 'utf-8')

def get_res(ind = 0):
    global Procs
    return b2s(Procs[ind].stdout.read())

def run_parsec(task, scale, n_thread, times, limited_time = 0):
    ws = '/root/tars/parsec-3.0'
    cur_path = os.getcwd()
    os.chdir('%s' % ws)
    cmd = 'time ./run.sh %s %s %d %d' % (task, scale, n_thread, times)
    t_total = 0
    nums = 1
    for i in range(0, nums):
        p = exec_cmd(cmd, wait = False)
        if limited_time != 0:
            time.sleep(limited_time)
            os.killpg(os.getpgid(p1.pid), signal.SIGTERM)
        else:
            p.wait()
        res = get_res()
        #print(res)
        if limited_time == 0:
            (m, s) = find_str2('real(.*)m(.*)s', res)
        else:
            (m, s) = ('0', str(limited_time))
        m = m.strip()
        s = s.strip()
        t = float(m) * 60 + float(s)
        t_total += t
    t_avg = t_total / nums
    os.chdir(cur_path)
    return t_avg

def run_parsec_parallel_pre(ind, task, scale, n_thread, times):
    ws = '/root/tars/parsec-3.0'
    cur_path = os.getcwd()
    os.chdir('%s' % ws)
    t_total = 0
    cmd = 'time ./run.sh %s %s %d %d' % (task, scale, n_thread, times)
    p1 = exec_cmd(cmd, ind + 20, wait = False)
    return p1

def run_parsec_parallel_post(ind, task, scale, n_thread, times):
    res = get_res(ind + 20)
    print(res)
    (m, s) = find_str2('real(.*)m(.*)s', res)
    t = float(m) * 60 + float(s)
    return t

def run_parsec_parallel(task, scale, n_thread, times, n_proc, limited_time = 0):
    ws = '/root/tars/parsec-3.0'
    cur_path = os.getcwd()
    os.chdir('%s' % ws)
    t_total = 0
    nums = 1
    for i in range(0, nums): # nums times same tasks
        cmd = 'time ./run.sh %s %s %d %d' % (task, scale, n_thread, times)
        p = parallel_cmd(cmd, n_proc, wait = False)
        if limited_time != 0:
            time.sleep(limited_time)
            for p1 in p:
                os.killpg(os.getpgid(p1.pid), signal.SIGTERM)
        else:
            for p1 in p:
                p1.wait()
        for j in range(0, n_proc):
            res = get_res(j)
            print(res)
            if limited_time == 0:
                (m, s) = find_str2('real(.*)m(.*)s', res)
            else:
                (m, s) = ('0', str(limited_time))
            print('Thread %d: %sm %ss' % (j, m, s))
            m = m.strip()
            s = s.strip()
            t = float(m) * 60 + float(s)
            t_total += t
        t_total /= n_proc
    t_avg = t_total / nums
    os.chdir(cur_path)
    return t_avg

def run_NPB_parallel(task_name, n_thread, n_proc, limited_time = 0):
    cmd = 'mpirun --version'
    exec_cmd(cmd)
    allow_root = ''
    if not 'mpich' in get_res():
        allow_root = '--allow-run-as-root'
    ws = '/root/NPB3.4.2/NPB3.4-MPI'
    cur_path = os.getcwd()
    os.chdir('%s' % ws)
    t_total = 0
    nums = 1
    for i in range(0, nums): # nums times same tasks
        if n_thread == 4:
            cmd = 'time mpirun %s -np %d bin/%s.B.x' % (allow_root, n_thread, task_name)
        elif n_thread == 8 or n_thread == 16:
            cmd = 'time mpirun %s -np %d bin/%s.C.x' % (allow_root, n_thread, task_name)
        p = parallel_cmd(cmd, n_proc, wait = False)
        if limited_time != 0:
            time.sleep(limited_time)
            for p1 in p:
                os.killpg(os.getpgid(p1.pid), signal.SIGTERM)
        else:
            for p1 in p:
                p1.wait()
        for j in range(0, n_proc):
            res = get_res(j)
            #print(res)
            if limited_time == 0:
                (m, s) = find_str2('real(.*)m(.*)s', res)
            else:
                (m, s) = ('0', str(limited_time))
            print('Thread %d: %sm %ss' % (j, m, s))
            m = m.strip()
            s = s.strip()
            t = float(m) * 60 + float(s)
            t_total += t
        t_total /= n_proc
    t_avg = t_total / nums
    os.chdir(cur_path)
    return t_avg

def run_mysql_parallel(n_thread, limited_time):
    ws = '/root/mysql-script/'
    cur_path = os.getcwd()
    os.chdir('%s' % ws)
    cmd = 'time ./test.sh %d %d' % (n_thread, limited_time)
    #cmd = 'cat test.out'
    exec_cmd(cmd)
    res = get_res()
    #print(res)
    qos = find_str2('queries: .* \(([0-9.]*) per sec.\)', res)
    print(qos)
    (m, s) = find_str2('real(.*)m(.*)s', res)
    m = m.strip()
    s = s.strip()
    t = float(m) * 60 + float(s)
    print(t)
    os.chdir(cur_path)
    return float(qos)

def run_memcached_parallel(n_thread, limited_time):
    cmd = 'ps aux | grep memcached'
    exec_cmd(cmd)
    lines = split_str(get_res(), '\n')
    mc_running = False
    for line in lines:
        if 'memcached' in line and not 'grep' in line:
            mc_running = True
    if not mc_running:
        cmd = 'memcached -d -m 1024 -u root'
        exec_cmd(cmd)
        print(get_res())
    cmd = 'memaslap -s 127.0.0.1:11211 -t %ds -T %d' % (limited_time, n_thread)
    exec_cmd(cmd)
    res = get_res()
    tps = find_str2('TPS: ([0-9.]*) ', res)
    print('tps:', tps)
    return float(tps)

beg_time = 0
end_time = 0

benchs = ['img-dnn', 'masstree', 'moses', 'silo', 'specjbb', 'xapian']
#begin_qps, end_qps, interval_qps, reqs, warmupreqs
ranges = [[250, 5000, 250, 10000, 5000], [1000, 15000, 1000, 3000, 14000], [5, 100, 5, 500, 500], [1000, 15000, 1000, 20000, 20000], [1000, 19000, 1000, 25000, 25000], [100, 1500, 100, 3000, 1000]]
max_qps = [1250, 5000, 10, 10000, 19000, 400]
standards = [8.464, 1.921, 28.874, 2.442, 0.537, 17.864]
proc_names = ['img-dnn', 'mttest', 'moses', 'dbtest', 'java', 'xapian']

def getLatPct(latsFile):
    assert os.path.exists(latsFile)
    latsObj = Lat(latsFile)
    sjrnTimes = [l/1e6 for l in latsObj.parseSojournTimes()]
    mnLt = np.mean(sjrnTimes)
    p95  = stats.scoreatpercentile(sjrnTimes, 95.0)
    return p95

def run_tailbench_parallel_pre(tail_id, bench_name, qps, reqs, warmupreqs, n_thread):
    os.chdir('/root/tars/tailbench-v0.9')
    global beg_time
    print('bench = %s, QPS = %d, REQS = %d, WARMUPREQS = %d' % (bench_name, qps, reqs, warmupreqs))
    beg_time = datetime.now()
    os.chdir('%s' % bench_name)
    p = exec_cmd('TBENCH_RANDSEED=1 ./myrun.sh %d %d %d %d' % (n_thread, qps, reqs, warmupreqs), tail_id, False)
    #print(get_res())
    os.chdir('..')
    return p

def run_tailbench_parallel_post(tail_id, bench_name, qps, reqs, warmupreqs, n_thread):
    os.chdir('/root/tars/tailbench-v0.9')
    global beg_time
    global end_time
    p95 = getLatPct("%s/lats.bin" % bench_name)
    tl = p95
    end_time = datetime.now()
    print('Time elapsed: %d s' % (end_time - beg_time).seconds)
    print('==================================================')
    sys.stdout.flush()
    sys.stderr.flush()
    return tl

def run_tailbench_parallel(tail_id, bench_name, qps, reqs, warmupreqs, n_thread):
    p = run_tailbench_parallel_pre(tail_id, bench_name, qps, reqs, warmupreqs, n_thread)
    p.wait()
    tl = run_tailbench_parallel_post(tail_id, bench_name, qps, reqs, warmupreqs, n_thread)
    return tl

def decode(data):
    pairs = data.split(',')
    res_dict = {}
    for pair in pairs:
        (first, second) = pair.split(':')
        res_dict[first] = second
    cmd = pairs[0].split(':')[0]
    return cmd, res_dict

if __name__ == '__main__':
    param = sys.argv[1]
    #parsec_scale = 'simlarge'
    #parsec_times = 10
    parsec_scale = 'native'
    parsec_times = 1
    parsec_threads = 16
    limited_time = 0
    if param == 'test':
        #benchs = ['splash2x.water_nsquared', 'splash2x.water_spatial', 'splash2x.raytrace', 'splash2x.ocean_cp', 'splash2x.ocean_ncp', 'splash2x.fmm', 'parsec.swaptions']
        benchs = ['parsec.blackscholes', 'parsec.canneal', 'parsec.fluidanimate', 'parsec.freqmine', 'parsec.streamcluster', 'parsec.vips']
        run_parsec_parallel('splash2x.ocean_ncp', parsec_scale, parsec_threads, parsec_times, 1)
        #run_parsec('splash2x.ocean_ncp', parsec_scale, parsec_threads, parsec_times)
        #run_parsec_parallel('4 parsec.ferret', parsec_scale, parsec_times, 18)
        #run_NPB_parallel('sp', 4, 1)
        #limited_time = 15
        #os.system("make run")
        #run_parsec_parallel('4 parsec.swaptions', parsec_scale, parsec_times, 1, limited_time)
        #run_NPB_parallel('sp', 4, 1, limited_time)
        #run_mysql_parallel(16, 20)
        #run_memcached_parallel(8, 20)
        #for bench_id in range(6, len(benchs)):
        #    run_parsec_parallel('4 %s' % benchs[bench_id], parsec_scale, parsec_times, 1)
    elif param == 'test_2':
        benchs = ['img-dnn', 'masstree', 'moses', 'silo', 'specjbb', 'xapian']
        ranges = [[250, 5000, 250, 10000, 5000], [1000, 15000, 1000, 3000, 14000], [5, 100, 5, 500, 500], [1000, 15000, 1000, 20000, 20000], [1000, 21000, 1000, 25000, 25000], [100, 1500, 100, 3000, 1000]]
        for ind in range(0, len(benchs)):
        #for ind in range(4, 5):
            bench = benchs[ind]
            ran = ranges[ind]
            for QPS in range(ran[0], ran[1], ran[2]):
                print('bench = %s, QPS = %d, REQS = %d, WARMUPREQS = %d' % (bench, QPS, ran[3], ran[4]))
                beg_time = datetime.now()
                os.chdir('%s' % bench)
                exec_cmd('TBENCH_RANDSEED=1 ./myrun.sh 1 %d %d %d' % (QPS, ran[3], ran[4]))
                print(get_res())
                os.chdir('..')
                getLatPct("%s/lats.bin" % bench)
                print(get_res())
                end_time = datetime.now()
                print('Time elapsed: %d s' % (end_time - beg_time).seconds)
                print('==================================================')
                sys.stdout.flush()
                sys.stderr.flush()
    elif param == 'test_3':
        p1 = run_tailbench_parallel_pre(10, 'img-dnn', 5000, 10000, 5000, 1)
        p2 = run_tailbench_parallel_pre(11, 'img-dnn', 5000, 10000, 5000, 1)
        #p3 = run_tailbench_parallel_pre(12, 'img-dnn', 5000, 10000, 5000, 16)
        #p4 = run_tailbench_parallel_pre(13, 'img-dnn', 5000, 10000, 5000, 16)
        p1.wait()
        p2.wait()
        #p3.wait()
        #p4.wait()
        run_tailbench_parallel_post(10, 'img-dnn', 5000, 10000, 5000, 1)
        run_tailbench_parallel_post(11, 'img-dnn', 5000, 10000, 5000, 1)
        #run_tailbench_parallel_post(12, 'img-dnn', 5000, 10000, 5000, 16)
        #run_tailbench_parallel_post(13, 'img-dnn', 5000, 10000, 5000, 16)
    elif param == 'test_4':
        ind = 5
        os.system('pkill %s' % (benchs[ind]))
        p1 = run_tailbench_parallel_pre(10 + ind, benchs[ind], max_qps[ind], ranges[ind][3] * 10, ranges[ind][4], 48)
        #p2 = run_tailbench_parallel_pre(11, 'img-dnn', 5000, 10000, 5000, 48)
        #p3 = run_tailbench_parallel_pre(12, 'img-dnn', 5000, 10000, 5000, 16)
        #p4 = run_tailbench_parallel_pre(13, 'img-dnn', 5000, 10000, 5000, 16)
        #time.sleep(0.1)
        #p1.send_signal(signal.SIGSTOP)
        exec_cmd('ps aux | grep %s' % (proc_names[ind]))
        pid = 0
        for line in split_str(get_res(), '\n'):
            if not 'grep' in line and not 'defunct' in line:
                print(line)
                pid = int(list(split_str(line))[1])
                print('pid = ', pid)
        #os.system('kill -STOP %d' % pid)
        #time.sleep(20)
        #os.system('kill -CONT %d' % pid)
        p1.wait()
        #p2.wait()
        #p3.wait()
        #p4.wait()
        run_tailbench_parallel_post(10 + ind, benchs[ind], max_qps[ind], ranges[ind][3] * 10, ranges[ind][4], 48)
        #run_tailbench_parallel_post(11, 'img-dnn', 5000, 10000, 5000, 48)
        #run_tailbench_parallel_post(12, 'img-dnn', 5000, 10000, 5000, 16)
        #run_tailbench_parallel_post(13, 'img-dnn', 5000, 10000, 5000, 16)
    elif param == 'run':
        debug = True
        port = 12345
        if len(sys.argv) > 2:
            port = int(sys.argv[2])
        serv = server.SERVER()
        if not debug:
            serv.set_port(port)
        serv.build()
        ind = 0
        while True:
            data = 0
            try:
                while True:
                    (cmd, data) = decode(serv.recv())
                    if cmd == 'begin':
                        serv.send('begin:0')
                    elif cmd == 'end':
                        serv.send('end:0')
                        break #modify file
                    elif cmd == 'all_end':
                        break
                    elif cmd == 'tasks' or cmd == 'limited_time':
                        print('cbw:', cmd, data)
                        if cmd == 'limited_time':
                            limited_time = 20
                        n_cores = data['num_cores']
                        task_name = data['task_name']
                        n_cores = int(n_cores.strip())
                        task_name = task_name.strip()
                        if 'tailbench' in task_name:
                            task_name = task_name.split('.')[1]
                            qps = int(data['qps'])
                            reqs = int(data['reqs'])
                            warmupreqs = int(data['warmupreqs'])
                            tl = run_tailbench_parallel(ind, task_name, qps, reqs, warmupreqs, n_cores)
                            ind += 1
                            serv.send('res:%f' % tl)
                        elif 'splash2x' in task_name or 'parsec' in task_name:
                            #if 'ocean_ncp' in task_name:    #special deal
                            #    num_threads = 4
                            #    tasks_per_thread = int(int(n_cores) / num_threads)
                            #    task = '%d %s' % (tasks_per_thread, task_name)
                            #else:
                            #    task = '4 %s' % task_name
                            #    num_threads = int(int(n_cores) / 4)
                            task = ''
                            num_threads = 0
                            if int(n_cores) == 4:
                                task = '4 %s' % task_name
                                num_threads = int(int(n_cores) / 4)
                            elif int(n_cores) == 8:
                                task = '8 %s' % task_name
                                num_threads = int(int(n_cores) / 8)
                            elif int(n_cores) == 16:
                                task = '16 %s' % task_name
                                num_threads = int(int(n_cores) / 16)
                            parsec_scale = data['scale']
                            parsec_threads = int(data['threads'])
                            #avg_perf = run_parsec(task, parsec_scale)
                            os.system('rm -rf /root/tars/parsec-3.0/result/*')
                            #os.system("make run")
                            avg_perf = run_parsec_parallel(task_name, parsec_scale, parsec_threads, parsec_times, 1, limited_time)
                            print(avg_perf, 's')
                            serv.send('res:%f' % avg_perf)
                        elif 'NPB' in task_name:
                            task_name = task_name[4:].lower()
                            num_threads = int(n_cores)
                            avg_perf = run_NPB_parallel(task_name, num_threads, 1, limited_time)
                            print(avg_perf, 's')
                            serv.send('res:%f' % avg_perf)
                        elif 'mysql' in task_name:
                            avg_perf = run_mysql_parallel(n_cores, limited_time)
                            print(avg_perf, 'queries/s')
                            serv.send('res:%f' % avg_perf)
                        elif 'memcached' in task_name:
                            avg_perf = run_mysql_parallel(n_cores * 8, limited_time)
                            print(avg_perf, 'TPS')
                            serv.send('res:%f' % avg_perf)
                if cmd == 'all_end':
                    serv.client_close()
                    serv.server_close()
                    break
            except KeyboardInterrupt:
                serv.client_close()
                serv.server_close()
                break
    else:
        print('param error')
