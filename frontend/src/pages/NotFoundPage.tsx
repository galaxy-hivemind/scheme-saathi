import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/common/Button';
import { Home } from 'lucide-react';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="flex flex-col items-center justify-center text-center py-20 px-4">
      <div className="text-7xl font-bold font-editorial text-navy/20 mb-2">404</div>
      <h2 className="text-2xl font-bold font-editorial text-navy mb-2">Page Not Found / पृष्ठ नहीं मिला</h2>
      <p className="text-sm text-navy/60 max-w-sm mb-6 leading-relaxed">
        The page you are looking for does not exist or has been moved.
      </p>
      <Link to="/">
        <Button variant="saffron" size="md" leftIcon={<Home className="w-4 h-4" />}>
          Return Home
        </Button>
      </Link>
    </div>
  );
};

