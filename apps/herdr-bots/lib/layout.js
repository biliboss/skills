import { layout } from 'herdr';

export function find(node, id) {
  if (!node) return null;
  if (node.id === id) return node;
  for (const child of node.children ?? []) {
    const found = find(child, id);
    if (found) return found;
  }
}

export function isNarrow() {
  return (find(layout(), 'sidebar')?.size?.px ?? 268) < 160;
}
