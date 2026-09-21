
import { BrowserRouter } from 'react-router-dom';
import { AppRouter } from './routes/AppRouter';
import './index.css'; // Design tokens and base styles
import { AuthProvider } from './contexts/AuthContext';
import { BranchProvider } from './contexts/BranchContext';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <BranchProvider>
          <AppRouter />
        </BranchProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
