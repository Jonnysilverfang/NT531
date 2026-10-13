"""Descriptive block-level progress figures, no interim inference or new samples."""
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(fig, directory, name):
    for suffix in ['png', 'svg']:
        path = directory / (name + '.' + suffix)
        fig.savefig(path, dpi=180)
        if suffix == 'svg':
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines()) + '\n', encoding='utf-8')
    plt.close(fig)


def main():
    sources = [ROOT / 'results/confirmation-rtt-v1/analysis.json',
               ROOT / 'results/application-slots-confirmation-v1/analysis.json']
    rtt, slots = [json.loads(p.read_text(encoding='utf-8-sig')) for p in sources]
    assert not rtt['issues'] and not slots['issues']
    out = ROOT / 'docs/images/application/confirmation-progress'
    out.mkdir(parents=True, exist_ok=True)
    if rtt['rows']:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), layout='constrained')
        blocks = [b['block'] for b in rtt['rows']]
        for row in rtt['rows']:
            axes[0].plot([row['block']] * 2, [row['peering_ms'], row['tgw_ms']], color='#b3bcc5', linewidth=1.5)
        for mode, color in [('peering', '#257aa9'), ('tgw', '#bd5f25')]:
            axes[0].scatter(blocks, [b[mode + '_ms'] for b in rtt['rows']], color=color, label=mode.upper(), zorder=3)
        axes[0].set_ylabel('Mean RTT per mode (ms)')
        axes[0].legend()
        axes[1].scatter(blocks, [b['difference_ms'] for b in rtt['rows']], color='#674b97', zorder=3)
        axes[1].axhline(.1, color='#a13a3a', linestyle='--', label='Prespecified margin 0.1 ms')
        axes[1].set_ylabel('TGW minus Peering (ms)')
        axes[1].legend(loc='best', fontsize=9)
        for ax in axes:
            ax.set_xticks(blocks); ax.set_xlabel('Validated block'); ax.grid(alpha=.2)
            ax.set_xlim(min(blocks) - .5, max(blocks) + .5)
        axes[0].set_ylim(bottom=0)
        minimum_difference = min(b['difference_ms'] for b in rtt['rows'])
        axes[1].set_ylim(bottom=min(0, minimum_difference - .05))
        fig.suptitle(f"RTT confirmation: {len(blocks)}/16 blocks — paired points within each block\nDescriptive snapshot; dates, order and missing replies reported separately", fontsize=12)
        save(fig, out, 'rtt-blocks')
    if slots['rows']:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), layout='constrained')
        blocks = [b['block'] for b in slots['rows']]
        for mode, color in [('peering', '#257aa9'), ('tgw', '#bd5f25')]:
            for count, marker in [(8, 'o'), (16, '^')]:
                values = []
                for block in slots['rows']:
                    condition = next(r for r in block['rows'] if (r['mode'], r['slots'], r['rate_rps']) == (mode, count, 800))
                    values.append(100 * condition['deadline_success_count'] / condition['scheduled'])
                # Horizontal offsets only for visibility; all points refer to the same block.
                offset = {('peering', 8): -.15, ('tgw', 8): -.05,
                          ('peering', 16): .05, ('tgw', 16): .15}[(mode, count)]
                axes[0].scatter([b + offset for b in blocks], values, color=color, marker=marker,
                                label=f'{mode.upper()}, {count} slots', zorder=3)
        axes[0].set_ylabel('Deadline success at 800 rps (%)')
        axes[0].legend(fontsize=9, loc='center right')
        axes[1].scatter(blocks, [100 * float(b['improvement']) for b in slots['rows']], color='#674b97', zorder=3)
        axes[1].axhline(10, color='#a13a3a', linestyle='--', label='Prespecified margin 10 pp')
        axes[1].set_ylabel('Slot improvement, mean over routes (pp)')
        axes[1].legend(loc='lower right', fontsize=9)
        for ax in axes:
            ax.set_xticks(blocks); ax.set_xlabel('Validated block'); ax.grid(alpha=.2)
            ax.set_xlim(min(blocks) - .5, max(blocks) + .5)
        axes[0].set_ylim(-3, 104); axes[1].set_ylim(-103, 104)
        fig.suptitle(f"Slots confirmation: {len(blocks)}/16 blocks — 50 ms deadline\nPoints shifted horizontally for visibility; whole blocks are the inferential units", fontsize=12)
        save(fig, out, 'slots-blocks')
    proof = dict(rtt_blocks=rtt['completed_blocks'], slots_blocks=slots['completed_blocks'],
                 scope='Descriptive block plots; no interim p-values, confidence intervals or early stopping',
                 sources=[dict(path=p.relative_to(ROOT).as_posix(), sha256=sha(p)) for p in sources],
                 figures=[dict(path=p.relative_to(ROOT).as_posix(), sha256=sha(p)) for p in sorted(out.glob('*'))])
    (ROOT / 'results/analysis/confirmation-progress-figures.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(rtt_blocks=rtt['completed_blocks'], slots_blocks=slots['completed_blocks'], output=str(out))))


if __name__ == '__main__':
    main()
