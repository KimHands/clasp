import cytoscape from 'cytoscape'
import fcose from 'cytoscape-fcose'

cytoscape.use(fcose)

export const LAYOUTS = {
  cluster: {
    name: 'fcose',
    quality: 'default',
    randomize: false,
    animate: true,
    animationDuration: 500,
    nodeSeparation: 75,
    idealEdgeLength: 100,
    nodeRepulsion: 4500,
    gravity: 0.25,
  },
  tree: {
    name: 'breadthfirst',
    directed: true,
    animate: true,
    animationDuration: 500,
    spacingFactor: 1.5,
    padding: 30,
  },
  force: {
    name: 'cose',
    animate: true,
    animationDuration: 500,
    nodeRepulsion: 8000,
    idealEdgeLength: 120,
    gravity: 1,
  },
}

export const CYTOSCAPE_STYLE = [
  // 카테고리 부모 노드 (compound)
  {
    selector: 'node[type="category"]',
    style: {
      'background-color': '#EFF6FF',
      'background-opacity': 0.7,
      'border-color': '#3B82F6',
      'border-width': 2,
      label: 'data(label)',
      'text-valign': 'top',
      'text-halign': 'center',
      'font-size': 13,
      'font-weight': 'bold',
      color: '#1D4ED8',
      'padding-top': 20,
      'padding-bottom': 20,
      'padding-left': 20,
      'padding-right': 20,
      shape: 'roundrectangle',
    },
  },
  // 파일 노드
  {
    selector: 'node[type="file"]',
    style: {
      'background-color': '#FFFFFF',
      'border-color': '#D1D5DB',
      'border-width': 1.5,
      label: 'data(label)',
      'text-valign': 'bottom',
      'text-halign': 'center',
      'font-size': 10,
      color: '#374151',
      width: 36,
      height: 36,
      shape: 'ellipse',
    },
  },
  // 신뢰도 낮은 파일 (31%~50%)
  {
    selector: 'node[type="file"][?lowConfidence]',
    style: {
      'background-color': '#FEF3C7',
      'border-color': '#F59E0B',
      'border-width': 2,
    },
  },
  // 미분류 파일 (31% 미만)
  {
    selector: 'node[type="file"][?unclassified]',
    style: {
      'background-color': '#FEE2E2',
      'border-color': '#EF4444',
      'border-width': 2,
    },
  },
  // 선택된 노드
  {
    selector: 'node:selected',
    style: {
      'border-color': '#2563EB',
      'border-width': 3,
      'background-color': '#DBEAFE',
    },
  },
  // 유사도 엣지
  {
    selector: 'edge[type="similarity"]',
    style: {
      'line-color': '#93C5FD',
      'line-style': 'dashed',
      width: 1.5,
      opacity: 0.6,
    },
  },
]

/**
 * 분류 결과 데이터를 Cytoscape 요소로 변환
 */
export function buildElements(files) {
  const elements = []
  const categorySet = new Set()

  files.forEach((file) => {
    const category = file.category || '미분류'
    categorySet.add(category)
  })

  // 카테고리 부모 노드
  categorySet.forEach((cat) => {
    elements.push({
      data: { id: `cat_${cat}`, label: cat, type: 'category' },
    })
  })

  // 파일 노드
  files.forEach((file) => {
    const category = file.category || '미분류'
    const isUnclassified = file.confidence_score < 0.31
    const isLowConfidence = !isUnclassified && file.confidence_score < 0.5

    elements.push({
      data: {
        id: `file_${file.id}`,
        label: file.filename.length > 15 ? file.filename.slice(0, 13) + '…' : file.filename,
        type: 'file',
        parent: `cat_${category}`,
        fileId: file.id,
        unclassified: isUnclassified,
        lowConfidence: isLowConfidence,
        confidence: file.confidence_score,
      },
    })
  })

  return elements
}
