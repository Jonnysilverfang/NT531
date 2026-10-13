"""Foreground waiting only; parses an explicit UTC ISO timestamp without locale conversion."""
import argparse
import datetime as dt
import time

def parse(value):
    instant=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if instant.tzinfo is None:raise ValueError('Explicit UTC offset required')
    return instant.astimezone(dt.timezone.utc)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('utc');args=p.parse_args()
    target=parse(args.utc)
    print('Wait until UTC '+target.isoformat(),flush=True)
    while dt.datetime.now(dt.timezone.utc)<target:
        time.sleep(min(30,max(0,(target-dt.datetime.now(dt.timezone.utc)).total_seconds())))
    print('UTC time reached',flush=True)
