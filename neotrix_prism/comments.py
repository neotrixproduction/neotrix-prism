"""Host-independent Neotrix file discussions (compatible with Blender schema 1)."""
import argparse
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path


def discussion_folder(filepath):
    path = Path(filepath)
    if not str(filepath).strip() or not path.is_file():
        raise ValueError('Choose an existing saved file before commenting.')
    return Path(str(path) + '.neotrix') / 'comments'


def load_comments(filepath):
    folder = discussion_folder(filepath)
    if not folder.exists():
        return [], []
    records, errors = [], []
    for path in sorted(folder.glob('*.json')):
        try:
            item = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(item, dict) or not all(isinstance(item.get(k), str) for k in ('id', 'author', 'text', 'created')):
                raise ValueError('Invalid comment record')
            datetime.fromisoformat(item['created'])
            records.append(item)
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f'{path.name}: {exc}')
    records.sort(key=lambda item: (datetime.fromisoformat(item['created']).replace(tzinfo=timezone.utc) if datetime.fromisoformat(item['created']).tzinfo is None else datetime.fromisoformat(item['created']), item['id']))
    return records, errors


def add_comment(filepath, author, message, application='Neotrix Prism'):
    author, message = author.strip(), message.strip()
    if not author or not message:
        raise ValueError('Enter your name and a comment.')
    if len(author) > 120 or len(message) > 12000:
        raise ValueError('Name or comment is too long.')
    folder = discussion_folder(filepath)
    folder.mkdir(parents=True, exist_ok=True)
    item = {'id': str(uuid.uuid4()), 'author': author, 'text': message,
            'created': datetime.now(timezone.utc).isoformat(), 'schema': 1,
            'application': application}
    pending = folder / (item['id'] + '.pending')
    try:
        with pending.open('x', encoding='utf-8') as handle:
            json.dump(item, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(pending, folder / (item['id'] + '.json'))
    finally:
        if pending.exists():
            pending.unlink()
    return item


def main():
    parser = argparse.ArgumentParser(description='Read or append shared Neotrix file comments.')
    parser.add_argument('filepath')
    parser.add_argument('--author')
    parser.add_argument('--message')
    parser.add_argument('--application', default='External app')
    args = parser.parse_args()
    try:
        result = add_comment(args.filepath, args.author or '', args.message, args.application) if args.message is not None else dict(zip(('comments', 'errors'), load_comments(args.filepath)))
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
