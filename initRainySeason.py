from app.agriculture.analysis.scripts.analysis_sp import init_rainy_season

def main():
    sep = ''.join(['-'] * 60)
    print(f'{sep}\n Computing rainy season: onset, cessation and length')
    init_rainy_season()
    print('Done!')

if __name__ == '__main__':
    main()

