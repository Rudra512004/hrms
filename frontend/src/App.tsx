
import { BrowserRouter } from 'react-router-dom';
import { AppRouter } from './routes/AppRouter';
import './index.css'; // Design tokens and base styles
import { AuthProvider } from './contexts/AuthContext';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRouter />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
