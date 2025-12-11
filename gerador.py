# license_generator.py
import argparse
import time
from superplayer_with_license import make_license, machine_id

def main():
    parser = argparse.ArgumentParser(description="Gerador de licença local (usar apenas em ambiente seguro)")
    parser.add_argument("--user", required=True, help="Nome do usuário/cliente")
    parser.add_argument("--days", type=int, default=365, help="Validade em dias")
    parser.add_argument("--bind", action="store_true", help="Amarrar licença à machine_id (recomendado)")
    parser.add_argument("--machine", default=None, help="Machine ID (se quiser gerar para uma máquina específica)")
    args = parser.parse_args()

    if args.bind and args.machine is None:
        print("Nenhuma machine_id informada -> usando machine_id local")
        target = machine_id()
    else:
        target = args.machine

    key = make_license(args.user, days_valid=args.days, bind_machine=args.bind, target_machine_id=target)
    print("LICENSE KEY:")
    print(key)
    if args.bind:
        print("\nEsta licença está amarrada ao machine_id:", target)
        print("Compartilhe o key e o machine_id (se for o caso) com o cliente.")

if __name__ == "__main__":
    main()
