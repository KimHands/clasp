/**
 * 분류 결과를 마인드맵 트리 데이터로 변환
 */

const CATEGORY_COLORS = {
  '문서': '#3B82F6',
  '프레젠테이션': '#F97316',
  '스프레드시트': '#22C55E',
  '데이터': '#A855F7',
  '코드': '#0EA5E9',
  '이미지': '#EAB308',
  '영상': '#F43F5E',
  '오디오': '#10B981',
  '압축': '#8B5CF6',
  '미분류': '#EF4444',
}

const CATEGORY_ICONS = {
  '문서': 'file-text',
  '프레젠테이션': 'presentation',
  '스프레드시트': 'table',
  '데이터': 'database',
  '코드': 'code',
  '이미지': 'image',
  '영상': 'video',
  '오디오': 'music',
  '압축': 'archive',
  '미분류': 'help-circle',
}

export function getCategoryColor(category) {
  return CATEGORY_COLORS[category] || '#6B7280'
}

export function getCategoryIcon(category) {
  return CATEGORY_ICONS[category] || 'file'
}

/**
 * 파일 목록 → 마인드맵 트리 구조 변환
 * { label, color, icon, type, children[], fileData? }
 */
export function buildMindmapTree(files, rootLabel = '스캔 결과') {
  const categoryMap = {}
  files.forEach((file) => {
    const category = file.category || '미분류'
    if (!categoryMap[category]) categoryMap[category] = []
    categoryMap[category].push(file)
  })

  const categoryNodes = Object.entries(categoryMap).map(([category, catFiles]) => {
    const color = getCategoryColor(category)

    const tagMap = {}
    const noTagFiles = []
    catFiles.forEach((file) => {
      if (file.tag) {
        if (!tagMap[file.tag]) tagMap[file.tag] = []
        tagMap[file.tag].push(file)
      } else {
        noTagFiles.push(file)
      }
    })

    const children = []

    Object.entries(tagMap).forEach(([tag, tagFiles]) => {
      children.push({
        id: `tag_${category}_${tag}`,
        label: tag,
        type: 'tag',
        color,
        icon: 'tag',
        children: tagFiles.map((f) => fileToNode(f, color)),
      })
    })

    noTagFiles.forEach((f) => {
      children.push(fileToNode(f, color))
    })

    return {
      id: `cat_${category}`,
      label: category,
      count: catFiles.length,
      type: 'category',
      color,
      icon: getCategoryIcon(category),
      children,
    }
  })

  return {
    id: 'root',
    label: rootLabel,
    type: 'root',
    color: '#1E293B',
    children: categoryNodes,
  }
}

function fileToNode(file, color) {
  return {
    id: `file_${file.id}`,
    label: file.filename,
    type: 'file',
    color,
    icon: file.confidence_score < 0.31 ? 'alert' : 'file',
    fileId: file.id,
    fileData: file,
    confidence: file.confidence_score,
    unclassified: file.confidence_score < 0.31,
    lowConfidence: file.confidence_score >= 0.31 && file.confidence_score < 0.5,
  }
}
