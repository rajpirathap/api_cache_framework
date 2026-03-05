import matplotlib.pyplot as plt
import numpy as np
import os

# Data from our evaluation runs
datasets = ['Synthetic', 'CICIDS2017', 'CSE-CIC-2018', 'UNSW-NB15']
recall = [1.00, 1.00, 1.00, 0.09]
accuracy = [1.00, 0.995, 0.996, 0.12]
precision = [1.00, 0.25, 0.08, 0.77]

x = np.arange(len(datasets))
width = 0.25

fig, ax = plt.subplots(figsize=(10, 6))
rects1 = ax.bar(x - width, recall, width, label='Recall', color='#2ca02c')
rects2 = ax.bar(x, accuracy, width, label='Accuracy', color='#1f77b4')
rects3 = ax.bar(x + width, precision, width, label='Precision', color='#ff7f0e')

ax.set_ylabel('Score (0-1)')
ax.set_title('CAS Performance Comparison Across Datasets')
ax.set_xticks(x)
ax.set_xticklabels(datasets)
ax.legend()
ax.set_ylim(0, 1.1)

# Add text labels
def autolabel(rects):
    for rect in rects:
        height = rect.get_height()
        ax.annotate(f'{height:.2f}',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=9)

autolabel(rects1)
autolabel(rects2)
autolabel(rects3)

fig.tight_layout()
os.makedirs('paper/figures', exist_ok=True)
plt.savefig('paper/figures/comparison_chart.pdf')
plt.close()
print("Generated paper/figures/comparison_chart.pdf")
