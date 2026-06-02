'use client';

import React from 'react';
import { Button, Card, Badge } from '../';
import { RefreshIcon, GlobeIcon } from '../ui/Icons';
import { BlogArticle } from '@/lib/api';

interface AEOBlogsListProps {
    blogs: BlogArticle[];
    onRefresh: () => void;
}

export const AEOBlogsList: React.FC<AEOBlogsListProps> = ({
    blogs,
    onRefresh
}) => {
    return (
        <Card
            title="Blog Articles"
            subtitle="Content from your Shopify blog"
            action={
                <Button
                    variant="outline"
                    size="sm"
                    onClick={onRefresh}
                    icon={<RefreshIcon size={16} />}
                >
                    Refresh
                </Button>
            }
        >
            {blogs.length === 0 ? (
                <div className="text-center py-16 text-zinc-400 bg-[#0a0a0a] rounded-sm border border-[#3a3a3a]">
                    <GlobeIcon size={48} className="mx-auto mb-4 opacity-50" />
                    <p>No blog articles found. Configure Shopify blog access in the backend.</p>
                </div>
            ) : (
                <div className="space-y-3">
                    {blogs.map((blog) => (
                        <div
                            key={blog.id}
                            className="flex justify-between items-center p-4 bg-[#0a0a0a] rounded-sm border border-[#3a3a3a]"
                        >
                            <div>
                                <h3 className="font-medium text-white">{blog.title}</h3>
                                <p className="text-sm text-zinc-400">{blog.url}</p>
                            </div>
                            <Badge variant={blog.include_in_llms_txt ? 'success' : 'default'}>
                                {blog.include_in_llms_txt ? 'Included' : 'Excluded'}
                            </Badge>
                        </div>
                    ))}
                </div>
            )}
        </Card>
    );
};
