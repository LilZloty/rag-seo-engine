import React from 'react';

export const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
        return (
            <div className="bg-[#111111] border border-[#222] p-3 shadow-lg">
                <p className="text-white font-medium mb-2">{label}</p>
                {payload.map((entry: any, index: number) => (
                    <p key={entry.dataKey || entry.name || `entry-${index}`} className="text-sm" style={{ color: entry.color }}>
                        {entry.name}: {typeof entry.value === 'number' ? entry.value.toLocaleString() : entry.value}
                    </p>
                ))}
            </div>
        );
    }
    return null;
};

export const FunnelTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
        const data = payload[0].payload;
        return (
            <div className="bg-[#111111] border border-[#222] p-3 shadow-lg">
                <p className="text-white font-medium">{data.name}</p>
                <p className="text-[#f7b500] text-lg font-bold">{data.value.toLocaleString()}</p>
                {data.fill && <p className="text-[#666666] text-xs">{Math.round((data.value / data.total) * 100)}% of total</p>}
            </div>
        );
    }
    return null;
};
