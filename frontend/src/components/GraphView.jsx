import { useEffect, useRef, useCallback } from 'react'
import cytoscape from 'cytoscape'
import { CYTOSCAPE_STYLE, LAYOUTS, buildElements } from '@/graph/cytoscapeConfig'

export default function GraphView({ files, layout = 'cluster', onNodeClick }) {
  const containerRef = useRef(null)
  const cyRef = useRef(null)

  const initCy = useCallback(() => {
    if (!containerRef.current || files.length === 0) return

    if (cyRef.current) {
      cyRef.current.destroy()
    }

    const elements = buildElements(files)

    cyRef.current = cytoscape({
      container: containerRef.current,
      elements,
      style: CYTOSCAPE_STYLE,
      layout: LAYOUTS[layout] || LAYOUTS.cluster,
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
    })

    // 파일 노드 클릭 이벤트
    cyRef.current.on('tap', 'node[type="file"]', (evt) => {
      const fileId = evt.target.data('fileId')
      onNodeClick?.(fileId)
    })

    // 배경 클릭 시 선택 해제
    cyRef.current.on('tap', (evt) => {
      if (evt.target === cyRef.current) {
        onNodeClick?.(null)
      }
    })
  }, [files, layout, onNodeClick])

  useEffect(() => {
    initCy()
    return () => {
      cyRef.current?.destroy()
    }
  }, [initCy])

  // 레이아웃만 변경할 때
  useEffect(() => {
    if (!cyRef.current) return
    cyRef.current.layout(LAYOUTS[layout] || LAYOUTS.cluster).run()
  }, [layout])

  return (
    <div
      ref={containerRef}
      className="w-full h-full rounded-xl bg-gray-50 border border-gray-200"
      style={{ minHeight: 480 }}
    />
  )
}
