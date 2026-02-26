import { HashRouter, Routes, Route } from 'react-router-dom'
import Home from '@/pages/Home'
import Scan from '@/pages/Scan'
import Result from '@/pages/Result'
import RuleManager from '@/pages/RuleManager'
import Settings from '@/pages/Settings'

// Electron 환경에서는 HashRouter 사용 (file:// 프로토콜 대응)
export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/scan" element={<Scan />} />
        <Route path="/result" element={<Result />} />
        <Route path="/rules" element={<RuleManager />} />
        <Route path="/apply" element={<Settings />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </HashRouter>
  )
}
