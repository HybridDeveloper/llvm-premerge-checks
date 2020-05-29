import argparse
import logging
import os
import uuid

from phabtalk.phabtalk import PhabTalk


def maybe_add_url_artifact(phab: PhabTalk, phid: str, url: str, name: str):
    if phid is None:
        logging.warning('PHID is not provided, cannot create URL artifact')
        return
    phab.create_artifact(phid, str(uuid.uuid4()), 'uri', {'uri': url, 'ui.external': True, 'name': name})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Runs premerge checks8')
    parser.add_argument('--url', type=str)
    parser.add_argument('--name', type=str)
    parser.add_argument('--phid', type=str)
    parser.add_argument('--log-level', type=str, default='WARNING')
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level, format='%(levelname)-7s %(message)s')
    phabtalk = PhabTalk(os.getenv('CONDUIT_TOKEN'), 'https://reviews.llvm.org/api/', False)
    maybe_add_url_artifact(phabtalk, args.phid, args.url, args.name)
