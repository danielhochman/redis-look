#!/usr/bin/env python2

from __future__ import division

import argparse
from collections import defaultdict
import itertools
import multiprocessing
import select
import signal
import sys
import time

import redis


def humanbytes(value, include_bytes=False):
    kilo, mega = 1024, 1024 ** 2
    if include_bytes and value < kilo:
        return '{}B'.format(value)
    elif value < mega:
        return '{:.1f}K'.format(value / kilo)
    else:
        return '{:.1f}M'.format(value / mega)


def get_client_from_args(args):
    return redis.StrictRedis(
        host=args['host'], port=args['port'], socket_timeout=1, socket_connect_timeout=1
    )


def monitor(args, stop_event):
    print 'Connecting...'
    client = get_client_from_args(args)
    connection = client.connection_pool.get_connection('MONITOR')
    print 'Issuing MONITOR...'
    connection.send_command('MONITOR')

    commands = []
    interval_start = 0
    while not stop_event.is_set():
        try:
            can_read = connection.can_read(timeout=1)
        except select.error:  # SIGINT
            can_read = False
        if can_read:
            commands.append(connection.read_response())

        if time.time() - interval_start > 0.5:
            # Output a nice counter
            interval_start = time.time()
            print '\r', 'Reading commands...', len(commands) - 1,
            sys.stdout.flush()
    client.connection_pool.release(connection)
    connection.disconnect()

    process_log(
        args,
        commands,
    )


def process_log(args, commands):
    if len(commands) <= 1:
        print '\nNothing to process'
        return

    # compute interval length for per-second
    start, end = float(commands[1].split()[0]), float(commands[-1].split()[0])
    elapsed = max(end - start, 1)
    total_commands = len(commands) - 1  # exclude OK preamble

    print '\n{} commands in {:0.2f} seconds ({:0.2f} cmd/s)'.format(
        total_commands, elapsed, total_commands / elapsed
    ),

    # count across dimensions
    results = defaultdict(lambda: defaultdict(int))
    for result in itertools.islice(commands, 1, None):
        split_result = result.strip().split()
        if len(split_result) > 4:
            # naively assume that the key is always in the 5th position
            # TODO: handle MGET, MSET, DEL
            # TODO: use https://github.com/antirez/redis-doc/blob/master/commands.json to determine key position
            command, key = split_result[3].strip('"').upper(), split_result[4].strip('"')
            results['0:key'][key] += 1
            results['1:command'][command] += 1
            results['2:command and key']['{} {}'.format(command, key)] += 1

    print 'across {} unique keys'.format(len(results['0:key']))

    # output summaries
    for result_type, result_values in sorted(results.iteritems()):
        result_type_pretty = result_type.partition(':')[-1]
        print '\n* top by {}\n'.format(result_type_pretty)
        print '{:>10}  {:>10}  {:>5}  {}'.format('count', 'avg/s', '%', result_type_pretty)
        for key, value in sorted(
                result_values.iteritems(), key=lambda item: item[1], reverse=True)[:args['summary_number']]:
            print '{:>10}  {:>10.2f}  {:>5.1f}  {}'.format(value, value / elapsed, 100 * value / total_commands, key)

    if args['estimate_throughput']:
        client = get_client_from_args(args)
        print '\nEstimating throughput requirements for top {} keys...'.format(args['estimate_throughput_limit'])

        overhead_bytes = 4  # estimate protocol overhead and help account for nil
        throughput_results = {}

        # ask Redis for size in bytes of top keys
        found_any_value = False
        for key, value in sorted(
                results['0:key'].iteritems(),
                key=lambda item: item[1], reverse=True)[:args['estimate_throughput_limit']]:
            try:
                throughput_req = client.debug_object(key)['serializedlength'] + overhead_bytes
                found_any_value = True
                time.sleep(0.001)
            except redis.ResponseError:  # no such key
                throughput_req = overhead_bytes  # nil
            throughput_results[key] = throughput_req * value, throughput_req

        # summarize
        if not found_any_value and args['input_file']:
            print '  No values found, is the host and port correct for throughput estimation?'
        else:
            result_type_pretty = 'est. throughput'
            print '* top by {}\n'.format(result_type_pretty)
            print '{:>11}  {:>10}  {:>10}  {:>12}  {}'.format(
                'est. bytes', 'count', 'throughput', 'throughput/s', 'key', result_type_pretty
            )
            for key, value in sorted(
                    throughput_results.iteritems(), key=lambda item: item[1][0], reverse=True)[:args['summary_number']]:
                total_throughput, estimated_size = value
                count = results['0:key'][key]
                print '{:>11}  {:>10}  {:>10}  {:>12}  {}'.format(
                    humanbytes(estimated_size, include_bytes=True),
                    count,
                    humanbytes(total_throughput),
                    humanbytes(total_throughput / elapsed),
                    key
                )


def main(args):
    if args['input_file']:
        with open(args['input_file']) as fh:
            process_log(args, fh.readlines())
        return

    # configure cleanup
    stop_event = multiprocessing.Event()
    signal.signal(signal.SIGINT, lambda _, __: stop_event.set())

    # spawn
    process = multiprocessing.Process(target=monitor, args=(args, stop_event))
    process.start()
    process.join()


if __name__ == '__main__':
    # TODO: fanout support (multiple remotes)
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--help', '-?', action='store_true')
    parser.add_argument('--host', '-h', default='localhost')
    parser.add_argument('--port', '-p', type=int, default=6379)
    parser.add_argument('--estimate-throughput', '-e', action='store_true')
    parser.add_argument('--estimate-throughput-limit', '-l', type=int, default=1000)
    parser.add_argument('--input-file', '-i')
    parser.add_argument('--summary-number', '-n', type=int, default=5)
    arguments = vars(parser.parse_args())

    if arguments['help']:
        parser.print_help()
        sys.exit(0)

    main(arguments)
