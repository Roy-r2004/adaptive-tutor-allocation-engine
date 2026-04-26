import { Navigate, Route, Routes } from 'react-router-dom'
import { Chat } from '@/app/routes/Chat'
import { Reviewer } from '@/app/routes/Reviewer'
import { TicketDetail } from '@/app/routes/TicketDetail'

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Chat />} />
      <Route path="/reviewer" element={<Reviewer />} />
      <Route path="/ticket/:id" element={<TicketDetail />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
