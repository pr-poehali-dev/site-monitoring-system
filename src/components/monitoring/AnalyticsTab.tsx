import { Card, CardContent } from '@/components/ui/card';
import Icon from '@/components/ui/icon';
import AnalyticsStatsCards from './analytics/AnalyticsStatsCards';
import AnalyticsSectionCharts from './analytics/AnalyticsSectionCharts';
import AnalyticsYearChart from './analytics/AnalyticsYearChart';
import AnalyticsPublicationChart from './analytics/AnalyticsPublicationChart';

interface AnalyticsTabProps {
  analytics: {
    by_section: { section: string; count: number }[];
    by_year: { year: number; count: number }[];
    by_year_section: { year: number; section: string; count: number }[];
    by_publication_date: { date: string; count: number }[];
    total_documents: number;
    total_files: number;
    documents_without_files: number;
    documents_with_multiple_files: number;
    total_size_mb: number | string;
  } | null;
}

const AnalyticsTab = ({ analytics }: AnalyticsTabProps) => {
  console.log('AnalyticsTab render:', analytics);
  
  if (!analytics) {
    return (
      <Card>
        <CardContent className="py-12">
          <div className="text-center text-gray-500">
            <Icon name="BarChart3" size={48} className="mx-auto mb-4 opacity-50" />
            <p>Загрузка аналитики...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <AnalyticsStatsCards analytics={analytics} />
      <AnalyticsSectionCharts analytics={analytics} />
      <AnalyticsYearChart analytics={analytics} />
      <AnalyticsPublicationChart analytics={analytics} />
    </div>
  );
};

export default AnalyticsTab;
