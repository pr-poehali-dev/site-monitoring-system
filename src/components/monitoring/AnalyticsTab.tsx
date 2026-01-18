import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import Icon from '@/components/ui/icon';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell } from 'recharts';

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

const COLORS = {
  'Постановления': '#3b82f6',
  'Распоряжения': '#10b981', 
  'Муниципальные программы': '#f59e0b'
};

const PIE_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

const AnalyticsTab = ({ analytics }: AnalyticsTabProps) => {
  const [selectedSectionFilter, setSelectedSectionFilter] = useState<string>('all');
  const [zoomRange, setZoomRange] = useState<'all' | '1year' | '6months' | '3months' | '1month'>('all');
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

  const formatSize = (mb: number | string) => {
    const mbNum = typeof mb === 'string' ? parseFloat(mb) : mb;
    if (mbNum >= 1024) return `${(mbNum / 1024).toFixed(2)} ГБ`;
    return `${mbNum.toFixed(2)} МБ`;
  };

  // Подготовка данных для графика "Документы по годам" с фильтром по разделам
  const getYearChartData = () => {
    if (!analytics) return [];
    
    if (selectedSectionFilter === 'all') {
      return analytics.by_year;
    }
    
    return analytics.by_year_section
      .filter(item => item.section === selectedSectionFilter)
      .map(item => ({ year: item.year, count: item.count }));
  };

  const yearChartData = getYearChartData();
  const totalInYearChart = yearChartData.reduce((sum, item) => sum + item.count, 0);

  // Фильтрация данных динамики публикаций по выбранному периоду
  const getPublicationChartData = () => {
    if (!analytics) return [];
    
    const now = new Date();
    const data = analytics.by_publication_date;
    
    if (zoomRange === 'all') return data;
    
    const daysMap: Record<string, number> = {
      '1month': 30,
      '3months': 90,
      '6months': 180,
      '1year': 365
    };
    
    const daysToShow = daysMap[zoomRange];
    return data.slice(-daysToShow);
  };

  const publicationChartData = getPublicationChartData();

  return (
    <div className="space-y-6">
      {/* Общая статистика */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <Icon name="FileText" size={24} className="mx-auto text-blue-600 mb-2" />
              <div className="text-3xl font-bold text-gray-900">{analytics.total_documents}</div>
              <div className="text-sm text-gray-500 mt-1">Документов</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <Icon name="Files" size={24} className="mx-auto text-green-600 mb-2" />
              <div className="text-3xl font-bold text-gray-900">{analytics.total_files}</div>
              <div className="text-sm text-gray-500 mt-1">Файлов</div>
              {analytics.documents_without_files > 0 && (
                <div className="text-xs text-orange-600 mt-1">
                  {analytics.documents_without_files} док. без файлов
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <Icon name="HardDrive" size={24} className="mx-auto text-orange-600 mb-2" />
              <div className="text-3xl font-bold text-gray-900">{formatSize(analytics.total_size_mb)}</div>
              <div className="text-sm text-gray-500 mt-1">Общий размер</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <Icon name="Layers" size={24} className="mx-auto text-purple-600 mb-2" />
              <div className="text-3xl font-bold text-gray-900">{analytics.by_section.length}</div>
              <div className="text-sm text-gray-500 mt-1">Разделов</div>
              {analytics.documents_with_multiple_files > 0 && (
                <div className="text-xs text-blue-600 mt-1">
                  {analytics.documents_with_multiple_files} док. с приложениями
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Информационная панель о файлах */}
      {analytics.documents_without_files > 0 && (
        <div className="p-4 border-2 border-orange-200 rounded-lg bg-orange-50">
          <div className="flex items-start gap-3">
            <Icon name="AlertCircle" size={18} className="text-orange-600 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-orange-900">
                Файлов ({analytics.total_files}) меньше, чем документов ({analytics.total_documents})
              </p>
              <p className="text-xs text-orange-700 mt-1">
                <strong>{analytics.documents_without_files} документов</strong> не имеют файлов в базе. 
                Это может быть связано с ошибками загрузки или документы были добавлены до внедрения системы файлов.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Распределение по разделам */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Документы по разделам</CardTitle>
            <CardDescription>Количество документов в каждом разделе</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={analytics.by_section}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis 
                  dataKey="section" 
                  tick={{ fontSize: 12 }}
                  angle={-15}
                  textAnchor="end"
                  height={80}
                />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: 'white', 
                    border: '1px solid #e5e7eb',
                    borderRadius: '8px'
                  }}
                />
                <Bar 
                  dataKey="count" 
                  fill="#3b82f6"
                  radius={[8, 8, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>

            <div className="mt-6 space-y-3">
              {analytics.by_section.map((item) => (
                <div key={item.section} className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex items-center gap-3">
                    <div 
                      className="w-3 h-3 rounded-full" 
                      style={{ backgroundColor: COLORS[item.section as keyof typeof COLORS] || '#94a3b8' }}
                    />
                    <span className="text-sm font-medium text-gray-900">{item.section}</span>
                  </div>
                  <Badge variant="secondary">{item.count} док.</Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Соотношение разделов</CardTitle>
            <CardDescription>Процентное распределение документов</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={analytics.by_section}
                  dataKey="count"
                  nameKey="section"
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  label={(entry) => `${entry.section}: ${entry.count}`}
                  labelLine={{ stroke: '#94a3b8', strokeWidth: 1 }}
                >
                  {analytics.by_section.map((entry, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={COLORS[entry.section as keyof typeof COLORS] || PIE_COLORS[index % PIE_COLORS.length]} 
                    />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: 'white', 
                    border: '1px solid #e5e7eb',
                    borderRadius: '8px'
                  }}
                />
              </PieChart>
            </ResponsiveContainer>

            <div className="mt-6 text-center">
              <div className="text-sm text-gray-500">
                Всего документов: <span className="font-semibold text-gray-900">{analytics.total_documents}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Распределение по годам */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Документы по годам</CardTitle>
              <CardDescription>Количество документов по годам публикации</CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">Всего: <span className="font-bold text-gray-900">{totalInYearChart}</span></span>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2 mb-4">
            <Button 
              variant={selectedSectionFilter === 'all' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSelectedSectionFilter('all')}
            >
              Все разделы
            </Button>
            {analytics.by_section.map((section) => (
              <Button 
                key={section.section}
                variant={selectedSectionFilter === section.section ? 'default' : 'outline'}
                size="sm"
                onClick={() => setSelectedSectionFilter(section.section)}
              >
                {section.section}
              </Button>
            ))}
          </div>

          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={yearChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis 
                dataKey="year" 
                tick={{ fontSize: 12 }}
              />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: 'white', 
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px'
                }}
              />
              <Bar 
                dataKey="count" 
                fill="#10b981"
                radius={[8, 8, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>

          <div className="mt-6 grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3">
            {yearChartData.map((item) => (
              <div key={item.year} className="p-3 border rounded-lg text-center hover:bg-gray-50 transition-colors">
                <div className="text-xs text-gray-500">{item.year}</div>
                <div className="text-lg font-bold text-gray-900 mt-1">{item.count}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Динамика публикаций */}
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4">
            <div>
              <CardTitle>Динамика публикаций документов</CardTitle>
              <CardDescription>Количество опубликованных документов по дням (последние 5 лет = {analytics.by_publication_date.length} дней)</CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="text-sm text-gray-600 mr-2 flex items-center">Период:</span>
              <Button 
                variant={zoomRange === 'all' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setZoomRange('all')}
              >
                <Icon name="Maximize2" size={14} className="mr-1" />
                Всё (5 лет)
              </Button>
              <Button 
                variant={zoomRange === '1year' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setZoomRange('1year')}
              >
                1 год
              </Button>
              <Button 
                variant={zoomRange === '6months' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setZoomRange('6months')}
              >
                6 месяцев
              </Button>
              <Button 
                variant={zoomRange === '3months' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setZoomRange('3months')}
              >
                3 месяца
              </Button>
              <Button 
                variant={zoomRange === '1month' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setZoomRange('1month')}
              >
                1 месяц
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={publicationChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis 
                dataKey="date" 
                tick={zoomRange === 'all' ? false : { fontSize: 10, angle: -45, textAnchor: 'end' }}
                height={zoomRange === 'all' ? 30 : 80}
                label={zoomRange === 'all' ? { value: 'Дата', position: 'insideBottom', offset: -5, style: { fontSize: 12 } } : undefined}
              />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: 'white', 
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px'
                }}
                labelFormatter={(value) => `Дата: ${value}`}
              />
              <Line 
                type="monotone" 
                dataKey="count" 
                stroke="#f59e0b" 
                strokeWidth={zoomRange === 'all' ? 1 : 2}
                dot={zoomRange === '1month' || zoomRange === '3months'}
                name="Документов"
              />
            </LineChart>
          </ResponsiveContainer>

          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="flex items-start gap-3">
                <Icon name="Info" size={18} className="text-blue-600 mt-0.5" />
                <div className="text-sm text-blue-900">
                  <p className="font-medium mb-1">Анализ динамики публикаций</p>
                  <p className="text-xs text-blue-700">
                    График показывает количество документов, опубликованных на сайте за каждый день (включая дни с 0 публикаций). 
                    Пики активности могут указывать на важные события или плановые публикации.
                  </p>
                </div>
              </div>
            </div>
            <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
              <div className="flex items-start gap-3">
                <Icon name="ZoomIn" size={18} className="text-green-600 mt-0.5" />
                <div className="text-sm text-green-900">
                  <p className="font-medium mb-1">Масштабирование графика</p>
                  <p className="text-xs text-green-700">
                    Выберите период для детального просмотра. На больших периодах (1-5 лет) точки скрыты для лучшей читаемости.
                    На коротких периодах (1-3 месяца) точки видны для точности.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AnalyticsTab;